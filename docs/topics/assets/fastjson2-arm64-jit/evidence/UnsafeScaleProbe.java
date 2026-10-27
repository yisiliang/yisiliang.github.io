import sun.misc.Unsafe;
import java.lang.reflect.Field;

public class UnsafeScaleProbe {
    static final Unsafe U;
    static final long BASE;
    static volatile long sink;
    static {
        try {
            Field f = Unsafe.class.getDeclaredField("theUnsafe");
            f.setAccessible(true);
            U = (Unsafe) f.get(null);
            BASE = U.arrayBaseOffset(char[].class);
        } catch (Exception e) { throw new RuntimeException(e); }
    }
    public static long read(char[] chars, int index) {
        return U.getLong(chars, BASE + ((long) index << 1));
    }
    public static void main(String[] args) {
        char[] chars = new char[4096];
        for (int i=0; i<chars.length; i++) chars[i]=(char)(0x1000+i);
        int index=4;
        long expected=0x1007100610051004L;
        System.out.println("java="+System.getProperty("java.runtime.version")+" charBase="+BASE);
        for (int i=0; i<1000000; i++) {
            long actual=read(chars,index);
            if (actual!=expected) {
                System.out.printf("FAIL iteration=%d index=%d expected=0x%016x actual=0x%016x actualFirstCharIndex=%d%n",i,index,expected,actual,(actual&65535)-0x1000);
                System.exit(1);
            }
            sink=actual;
        }
        System.out.println("PASS reads=1000000 expected=0x1007100610051004");
    }
}
