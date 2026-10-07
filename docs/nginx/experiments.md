# NGINX隔离实验

截至2026年10月7日，本书没有安装、编译或启动NGINX；以下配置、curl与信号实验**未执行**。已执行Python后端语法/本地响应核验，不能据此把NGINX实验标为通过。请使用自行准备的匹配1.28.0构建；`nginx -V`核对HTTP proxy/cache/limit_req、平台事件模块及可选SSL/stub_status。不同模块裁剪会使配置不被接受。

实验都绑定127.0.0.1。默认端口18080/18081应先确认空闲；18082刻意不监听，用作连接拒绝。不要对其他NGINX实例发送信号，也不要复制到生产。后端仅模拟GET和带Content-Length的POST，不实现chunked body解码。

## 1. 准备目录与启动

在解压目录中执行：

```sh
LAB="$(mktemp -d /tmp/nginx-source-lab.XXXXXX)"
mkdir -p "$LAB/conf" "$LAB/logs" "$LAB/temp/body" "$LAB/temp/proxy" "$LAB/cache" "$LAB/html/static"
cp lab-nginx.conf "$LAB/conf/nginx.conf"
python3 -c 'from pathlib import Path; import sys; Path(sys.argv[1]).write_bytes(b"x" * 1048576)' "$LAB/html/static/large.bin"
python3 lab-backend.py --port 18081
```

后端前台运行；在另一个终端将上一终端的LAB路径赋到变量，再执行：

```sh
nginx -V
nginx -t -p "$LAB/" -c conf/nginx.conf
nginx -p "$LAB/" -c conf/nginx.conf
curl -i http://127.0.0.1:18080/version
```

预期版本文本为nginx-lab-v1，最终结果以运行日志和实际响应为准。若端口、目录权限或构建不符，应先解决再继续。

## 2. 路由、内部跳转与分片解析

```sh
curl -i 'http://127.0.0.1:18080/version?x=1'
curl -i 'http://127.0.0.1:18080/prefix/a.txt'
curl -i 'http://127.0.0.1:18080/old'
python3 - <<'PY'
import socket,time
with socket.create_connection(('127.0.0.1',18080)) as s:
    s.sendall(b'GET /ver'); time.sleep(0.2)
    s.sendall(b'sion HTTP/1.1\r\nHost: lab.local\r\nConnection: close\r\n\r\n')
    chunks=[]
    while True:
        b=s.recv(65536)
        if not b: break
        chunks.append(b)
    print(b''.join(chunks).decode(errors='replace'))
PY
```

预期version忽略query进行location选择，a.txt命中顶层regex，old内部跳到version；access日志的request_uri和uri不同。把`location /prefix/`改为`location ^~ /prefix/`，检测并reload后应走prefix。配置内部跳转循环时应500；实验完成恢复原配置。

## 3. 上游连接拒绝与重试

```sh
curl -i http://127.0.0.1:18080/retry/demo
```

primary端口18082无人监听时，可尝试backup18081。查看access日志upstream_addr等是否多值，以及error里的connect failed。将proxy_next_upstream改为off再检测/reload后比较。由于被动失败状态可能跳过暂不可用primary，后续请求不一定仍记录两次尝试，需等待fail_timeout或重新建worker。

POST禁止无条件业务重试。只使用虚构echo端点，并分别记录请求是否已发送、body是否buffered、是否显式允许non_idempotent；不能从一次观察推出所有POST场景。不要在真实提交接口重复试验。

## 4. 缓存有效期与限流

```sh
curl -i http://127.0.0.1:18080/cache/demo
curl -i http://127.0.0.1:18080/cache/demo
sleep 3
curl -i http://127.0.0.1:18080/cache/demo
python3 - <<'PY'
import urllib.request,urllib.error
for i in range(8):
    try:
        with urllib.request.urlopen('http://127.0.0.1:18080/limit/demo') as r: print(i,r.status)
    except urllib.error.HTTPError as e: print(i,e.code)
PY
```

缓存头预期MISS/HIT/过期回源，后端time_ns可辅助验证内容复用。准确过期边界取决于实际请求时间和headers。限流使用同一IP、2r/s、burst2、nodelay，可能出现429；不承诺固定第几个拒绝。`/limit/`经proxy处理，不能改成return200后仍期望PREACCESS限流照常执行。

## 5. 读间隔超时、慢客户端和请求体

```sh
curl -N -v 'http://127.0.0.1:18080/slow?gap=0.2'
curl -N -v 'http://127.0.0.1:18080/slow?gap=2'
curl --limit-rate 32k -o /dev/null -v 'http://127.0.0.1:18080/blob?size=8388608'
curl --limit-rate 32k -o /dev/null -v 'http://127.0.0.1:18080/static/large.bin'
python3 -c 'from pathlib import Path; Path("payload.bin").write_bytes(b"x" * 131072)'
curl --data-binary @payload.bin --limit-rate 16k http://127.0.0.1:18080/echo
```

gap2超过1s读间隔；响应头已经发送时curl可报告body不完整，不能期待所有超时都收到完整504。gap0.2总体可能超过1s而仍成功。更改buffering/request_buffering要独立比较后端日志、temp目录、上游连接持续时间；本页未记录吞吐测试结果。

## 6. reload与退出

```sh
# 手工将 /version 返回文本改为 v2 后：
nginx -t -p "$LAB/" -c conf/nginx.conf
nginx -p "$LAB/" -c conf/nginx.conf -s reload
curl -i http://127.0.0.1:18080/version
# 全部实验结束后，只退出此lab：
nginx -p "$LAB/" -c conf/nginx.conf -s quit
```

观察日志及PID、运行中的slow请求。USR2二进制热升级、TLS、DNS动态解析、Linux系统调用跟踪和大并发压测没有提供“一键执行”脚本，需先建立对应隔离环境，按手册定位点复现。清理前确认lab进程已退出；目录可保留作证据，勿盲清/tmp。
