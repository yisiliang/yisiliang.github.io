import com.alibaba.fastjson2.JSON;
import com.alibaba.fastjson2.util.IOUtils;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;

public class FastjsonProbe {
    static volatile long sink;
    public static void main(String[] args) throws Exception {
        int count = args.length == 0 ? 1000000 : Integer.parseInt(args[0]);
        System.out.println("java=" + System.getProperty("java.runtime.version")
                + " vm=" + System.getProperty("java.vm.name")
                + " os=" + System.getProperty("os.name")
                + " arch=" + System.getProperty("os.arch")
                + " fastjson=" + JSON.VERSION);
        char[] chars = new char[1031];
        byte[] bytes = new byte[1031];
        for (int i = 0; i < chars.length; i++) {
            chars[i] = (char) ((i * 7919 + 12345) & 65535);
            bytes[i] = (byte) (i * 37 + 11);
        }
        long[] expectedChars = new long[chars.length - 3];
        long[] expectedBytes = new long[bytes.length - 7];
        for (int i = 0; i < expectedChars.length; i++) {
            long v = 0;
            for (int j = 0; j < 4; j++) v |= ((long) chars[i+j]) << (j*16);
            expectedChars[i] = v;
        }
        for (int i = 0; i < expectedBytes.length; i++) {
            long v = 0;
            for (int j = 0; j < 8; j++) v |= (bytes[i+j] & 255L) << (j*8);
            expectedBytes[i] = v;
        }
        long started = System.nanoTime();
        for (int i = 0; i < count * 10L; i++) {
            int ci = i % expectedChars.length, bi = i % expectedBytes.length;
            long c = IOUtils.getLongLE(chars, ci), b = IOUtils.getLongLE(bytes, bi);
            if (c != expectedChars[ci] || b != expectedBytes[bi])
                throw new AssertionError("getLongLE mismatch iteration=" + i + " charOffset=" + ci + " byteOffset=" + bi);
            sink = c ^ b;
        }
        System.out.println("PASS getLongLE char[] + byte[] checks=" + count * 20L);
        String longUrl = "consumer://service/" + repeat("abcdefgh01234567", 48);
        String[] cases = {
            "{\"messageId\":\"test-123\",\"message\":[\"consumer://service/path?key=value\"]}",
            "{\"messageId\":\"test-long\",\"message\":[\"" + longUrl + "\"]}",
            "{\"messageId\":\"test-unicode\",\"message\":[\"consumer://中文服务/测试\",\"quote=\\\" slash=\\\\ line=\\n unicode=\\u4e2d\"]}"
        };
        if (args.length > 1) cases = new String[] {new String(Files.readAllBytes(Paths.get(args[1])), StandardCharsets.UTF_8)};
        for (int k = 0; k < cases.length; k++) {
            final String input = cases[k];
            final Object expected = JSON.parse(input);
            for (int i = 0; i < count; i++) {
                try {
                    Object actual = JSON.parse(input);
                    if (!expected.equals(actual)) throw new AssertionError("parsed value mismatch");
                } catch (Throwable error) {
                    System.err.println("FAIL case=" + k + " length=" + input.length() + " iteration=" + i);
                    throw error;
                }
            }
            System.out.println("PASS JSON.parse case=" + k + " chars=" + input.length() + " iterations=" + count);
        }
        System.out.println("PASS elapsedSeconds=" + (System.nanoTime()-started)/1e9 + " sink=" + sink);
    }
    static String repeat(String s, int n) {
        StringBuilder b = new StringBuilder();
        for (int i = 0; i < n; i++) b.append(s);
        return b.toString();
    }
}
