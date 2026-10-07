# 两个会话：从预期到源码条件

状态：实验脚本已经静态检查，**未在本机执行**。不要把下列值、错误或等待写进实测报告。运行`lab.sql`初始化后，用两个独立连接A/B，均执行`USE source_lab`。监控查询使用第三个连接C。小表执行计划可能选择全扫，锁范围实验因此使用FORCE INDEX固定访问路径；这是机制实验，不是生产调优建议。

## 1.RR：首次一致性读创建视图

| 顺序 | 会话A | 会话B | 预期/源码依据 |
|---|---|---|---|
| 1 | `SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ; START TRANSACTION;` | | BEGIN本身通常不创建普通一致性读快照 |
| 2 | `SELECT balance FROM account WHERE id=1;` | | 记值为v；`trx_assign_read_view`创建视图 |
| 3 | | `START TRANSACTION; UPDATE account SET balance=balance+10 WHERE id=1; COMMIT;` | B更新生成undo/redo并提交 |
| 4 | `SELECT balance FROM account WHERE id=1;` | | 仍为v，B版本不符合旧视图，追undo |
| 5 | `SELECT balance FROM account WHERE id=1 FOR UPDATE;` | | 锁定读预期为v+10；它不是旧视图一致性读 |
| 6 | `ROLLBACK;` | | 释放视图与锁；A未修改余额 |

替代调度：A先BEGIN，B先更新提交，A才首次普通SELECT；应看到B提交后的值。这反证“所有RR事务在BEGIN创建快照”。用WITH CONSISTENT SNAPSHOT则需另外核对该入口。

## 2.RC：每语句一致性读更新边界

A设置READ COMMITTED并开启事务，先普通SELECT记值v。B更新id=1并提交。A下一次普通SELECT预期看到v+10。A随后ROLLBACK。读视图由语句结束释放/后续重新获取，不意味着RC会直接读取其他事务尚未提交的值。

## 3.RR范围锁：先锁住范围，再尝试插入

A：

```sql
SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ;
START TRANSACTION;
SELECT * FROM account FORCE INDEX(idx_tenant_balance)
 WHERE tenant_id=10 AND balance BETWEEN 100 AND 250 FOR UPDATE;
```

B：

```sql
SET SESSION innodb_lock_wait_timeout=5;
START TRANSACTION;
INSERT INTO account VALUES(99,10,150,'gap-test');
```

预期B可能因A范围中的gap/next-key锁等待。C查询data_locks与data_lock_waits，记录索引名、mode和阻塞事务；不要只看SQL文字推断锁集合。A完成ROLLBACK后，若B已超时，B执行ROLLBACK；若B成功则也ROLLBACK，保持测试数据不变。id=99已有数据时应换一个未使用ID。

## 4.死锁：形成明确的等待环

1.A开启事务，`UPDATE account SET balance=balance+1 WHERE id=1;`。
2.B开启事务，`UPDATE account SET balance=balance+1 WHERE id=2;`。
3.A执行`UPDATE account SET balance=balance+1 WHERE id=2;`，此命令等待，保持终端。
4.B执行`UPDATE account SET balance=balance+1 WHERE id=1;`。
5.开启innodb_deadlock_detect时，预期其中一个会话收到1213/SQLSTATE40001；不能事先承诺一定是B。
6.两个会话均ROLLBACK，C查看`SHOW ENGINE INNODB STATUS`最近死锁信息。

源码依据是等待图环校验与lock_wait_choose_victim权重/优先级分支。若检测关闭，会表现为超时，先记录配置。业务重试应重新执行完整事务，不能只重跑最后一条SQL。

## 5.MDL：没有行锁也会挡住DDL

A开启事务并普通SELECT account一行，保持事务。B执行`ALTER TABLE account ADD COLUMN lab_marker INT NULL;`，预期等待A持有的事务MDL。C查metadata_locks的GRANTED/PENDING，而不是data_locks。A ROLLBACK后B应继续；DDL完成后验证列再决定是否删除实验列。该步骤真的修改表结构，需独立测试库。

## 6.长视图与purge：观察趋势，不伪造计数

A在RR下第一次一致性读后不结束。B对id=1做若干次独立UPDATE/COMMIT。C采样INNODB STATUS历史长度及innodb_trx最老事务，记录每次时点。A ROLLBACK后再采样，预期历史清理边界获得推进机会；不保证立即归零，也不保证文件立即变小。其他事务、后台调度与写入都会影响数值。

## 7.持久化和复制实验的边界

只读取`@@innodb_flush_log_at_trx_commit`、`@@sync_binlog`、`@@log_bin`与当前状态，不修改全局策略。这里没有执行进程kill、断电、手工删redo或binlog，也没有部署复制拓扑。章节中的crash/debug窗口属于**源码纸面推演**，需要debug构建及隔离故障环境才能动态验证。普通安装包中的DBUG代码可能被编译掉。
