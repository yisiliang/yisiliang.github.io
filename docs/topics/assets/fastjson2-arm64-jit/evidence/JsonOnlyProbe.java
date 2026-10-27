import com.alibaba.fastjson2.JSON;

public class JsonOnlyProbe {
    public static void main(String[] args) {
        int count = Integer.parseInt(args[0]);
        String url = "consumer://service/" + FastjsonProbe.repeat("abcdefgh01234567", 48);
        String[] cases = {
            "{\"messageId\":\"test-123\",\"message\":[\"consumer://service/path?key=value\"]}",
            "{\"messageId\":\"test-long\",\"message\":[\"" + url + "\"]}",
            "{\"messageId\":\"test-unicode\",\"message\":[\"consumer://中文服务/测试\",\"quote=\\\" slash=\\\\ line=\\n unicode=\\u4e2d\"]}"
        };
        System.out.println("java=" + System.getProperty("java.runtime.version") + " arch=" + System.getProperty("os.arch"));
        for (int k=0; k<cases.length; k++) {
            final String input = cases[k];
            Object expected = JSON.parse(input);
            for (int i=0; i<count; i++) {
                try {
                    Object actual = JSON.parse(input);
                    if (!expected.equals(actual)) throw new AssertionError("parsed result mismatch");
                } catch (Throwable t) {
                    System.err.println("FAIL JSON case=" + k + " iteration=" + i + " chars=" + input.length());
                    throw t;
                }
            }
            System.out.println("PASS JSON case=" + k + " iterations=" + count);
        }
    }
}
