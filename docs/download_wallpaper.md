
# 每天自动下载Bing的首页图片当做墙纸(MacOS)

## 脚本

```bash
#!/bin/sh

BING_PING_HOST="cn.bing.com"
BING_BASE_URL="https://$BING_PING_HOST"
WALLPAPERS_BASE_FOLDER="/Users/$USER/Pictures/wallpapers"

INTERVAL=1

checkWan() {
    i=1
    while [ $i -lt 5 ]; do
        /sbin/ping -c 1 $BING_PING_HOST 1>/dev/null 2>/dev/null
        if [ $? -eq 0 ]; then
            return 0
        else
            echo "[$(date)]$i can not connect to $BING_PING_HOST" 
            sleep $INTERVAL
        fi
        i=$(expr $i + 1)
    done
    return 1
}

checkWan
if [ $? -eq 0 ]; then
    echo "[$(date)]status ok." 

    filename="$WALLPAPERS_BASE_FOLDER/$(date "+%Y%m%d.jpg")"
    if [ -f $filename ]; then
        echo "$filename exists, return."
        exit 0
    fi
    echo $filename
    #提取壁纸图片URL
    url="$(curl $BING_BASE_URL 2>/dev/null | grep "link id=\"bgLink\"" | head -1 | sed 's/\.jpg.*$/\.jpg/g' | sed 's/^.*href=\"//g')"
    #拼接完整图片URL
    url="${BING_BASE_URL}${url}"
    echo $url
    #下载图片至本地
    curl -o $filename $url 1>/dev/null 2>/dev/null
    #调用Finder应用切换桌面壁纸
    osascript -e "tell application \"Finder\" to set desktop picture to POSIX file \"$filename\""
    echo "changed completed."
else
    echo "[$(date)]can not connect to $BING_BASE_URL" 
fi
```

## crontab

```bash
*/10 * * * * /path/to/yourscript.sh
```
