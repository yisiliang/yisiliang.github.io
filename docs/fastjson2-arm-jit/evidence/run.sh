#!/bin/sh
set -u
cd "$(dirname "$0")"
runtime="${1:-java}"
compiler="${2:-javac}"
if [ ! -f fastjson2-2.0.61.jar ]; then
    echo '请先按 README 下载并校验 fastjson2-2.0.61.jar' >&2
    exit 2
fi
"$compiler" -source 8 -target 8 -cp fastjson2-2.0.61.jar ./*.java || exit 2
run_dir=$(mktemp -d './runs-XXXXXX')
"$runtime" -version > "$run_dir/environment.log" 2>&1
uname -a >> "$run_dir/environment.log"
run() {
    label="$1"
    shift
    "$runtime" -Xmx512m "$@" > "$run_dir/$label.log" 2>&1
    code=$?
    printf '%s exit=%s log=%s/%s.log\n' "$label" "$code" "$run_dir" "$label"
}
run scale -Xbatch '-XX:CompileCommand=compileonly,UnsafeScaleProbe::read' '-XX:CompileCommand=print,UnsafeScaleProbe::read' -cp . UnsafeScaleProbe
run char -cp .:fastjson2-2.0.61.jar LongReadProbe char
run byte -cp .:fastjson2-2.0.61.jar LongReadProbe byte
run json-jit -XX:+PrintCompilation -cp .:fastjson2-2.0.61.jar JsonOnlyProbe 1000000
run json-xcomp -Xcomp -cp .:fastjson2-2.0.61.jar JsonOnlyProbe 1000000
run scale-xcomp -Xcomp -cp . UnsafeScaleProbe
run json-xint -Xint -cp .:fastjson2-2.0.61.jar JsonOnlyProbe 100000
run json-c1 -XX:TieredStopAtLevel=1 -cp .:fastjson2-2.0.61.jar JsonOnlyProbe 1000000
run json-exclude '-XX:CompileCommand=exclude,com.alibaba.fastjson2.util.IOUtils::getLongLE' -cp .:fastjson2-2.0.61.jar JsonOnlyProbe 1000000
