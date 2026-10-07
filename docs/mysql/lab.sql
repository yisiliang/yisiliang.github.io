-- MySQL8.4源码学习实验；未在本机执行。
-- 仅连接隔离测试实例。创建独立source_lab，不删除现有数据库。
SELECT VERSION(), @@transaction_isolation, @@autocommit;
CREATE DATABASE IF NOT EXISTS source_lab;
USE source_lab;
CREATE TABLE IF NOT EXISTS account (
  id BIGINT PRIMARY KEY,
  tenant_id INT NOT NULL,
  balance DECIMAL(12,2) NOT NULL,
  note VARCHAR(64) NOT NULL,
  KEY idx_tenant_balance (tenant_id, balance)
) ENGINE=InnoDB;
-- INSERT IGNORE让初始化可重复；若旧实验修改过值，请检查后手工重置。
INSERT IGNORE INTO account VALUES
 (1,10,100.00,'alpha'),(2,10,200.00,'beta'),
 (3,20,300.00,'gamma'),(4,20,400.00,'delta');
SELECT * FROM account ORDER BY id;
EXPLAIN FORMAT=TREE SELECT id,balance FROM account
 WHERE tenant_id=10 AND balance>=100 ORDER BY balance;
-- ANALYZE会真实执行SELECT；少量数据可能使优化器选全扫，不能强行声称走索引。
EXPLAIN ANALYZE SELECT id,balance FROM account
 WHERE tenant_id=10 AND balance>=100 ORDER BY balance;
SET optimizer_trace='enabled=on';
SELECT id,note FROM account WHERE tenant_id=10 AND balance>=100;
SELECT TRACE FROM information_schema.OPTIMIZER_TRACE;
SET optimizer_trace='enabled=off';
-- 以下诊断需相应监控权限；在会话产生等待后从第三个会话执行。
SELECT ENGINE_TRANSACTION_ID, OBJECT_SCHEMA, OBJECT_NAME, INDEX_NAME,
       LOCK_TYPE, LOCK_MODE, LOCK_STATUS, LOCK_DATA
FROM performance_schema.data_locks WHERE OBJECT_SCHEMA='source_lab';
SELECT * FROM performance_schema.data_lock_waits;
SELECT OBJECT_TYPE,OBJECT_SCHEMA,OBJECT_NAME,LOCK_TYPE,LOCK_DURATION,LOCK_STATUS,
       OWNER_THREAD_ID FROM performance_schema.metadata_locks
 WHERE OBJECT_SCHEMA='source_lab';
SELECT trx_id,trx_state,trx_started,trx_mysql_thread_id,trx_query
 FROM information_schema.innodb_trx;
SHOW ENGINE INNODB STATUS;
SHOW GLOBAL STATUS WHERE Variable_name IN
 ('Innodb_buffer_pool_read_requests','Innodb_buffer_pool_reads',
  'Innodb_buffer_pool_wait_free','Innodb_buffer_pool_pages_dirty',
  'Innodb_os_log_written','Innodb_log_waits');
SELECT * FROM performance_schema.replication_applier_status_by_worker;
-- 完成两会话实验后，每个会话ROLLBACK/COMMIT，再退出；不要只关闭当前查询。
