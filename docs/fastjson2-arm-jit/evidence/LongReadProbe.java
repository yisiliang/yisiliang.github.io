import com.alibaba.fastjson2.util.IOUtils;

public class LongReadProbe {
    static volatile long sink;
    public static void main(String[] args) {
        boolean charMode = "char".equals(args[0]);
        char[] chars = new char[1031];
        byte[] bytes = new byte[1031];
        for (int i=0; i<chars.length; i++) {
            chars[i] = (char)((i*7919+12345)&65535);
            bytes[i] = (byte)(i*37+11);
        }
        long[] expected = new long[charMode ? chars.length-3 : bytes.length-7];
        for (int i=0; i<expected.length; i++) {
            long v=0;
            for (int j=0; j<(charMode?4:8); j++)
                v |= (charMode ? (long)chars[i+j] : bytes[i+j]&255L) << (j*(charMode?16:8));
            expected[i]=v;
        }
        for (int i=0; i<10000000; i++) {
            int offset = i%expected.length;
            long actual = charMode ? IOUtils.getLongLE(chars,offset) : IOUtils.getLongLE(bytes,offset);
            if (actual != expected[offset]) {
                throw new AssertionError(String.format("mode=%s iteration=%d offset=%d expected=0x%016x actual=0x%016x",args[0],i,offset,expected[offset],actual));
            }
            sink=actual;
        }
        System.out.println("PASS mode="+args[0]+" reads=10000000 sink="+sink);
    }
}
