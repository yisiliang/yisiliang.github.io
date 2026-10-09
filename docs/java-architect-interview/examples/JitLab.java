import java.util.concurrent.CyclicBarrier;
import java.util.concurrent.atomic.AtomicInteger;

/** Small teaching experiments; not a benchmark or a proof of concurrency safety. */
public final class JitLab {
    private static boolean plainRunning = true;
    private static volatile boolean volatileRunning = true;
    private static volatile int count;
    private static int data;
    private static volatile boolean ready;

    interface Op { int apply(int x); }
    static final class PlusOne implements Op {
        public int apply(int x) { return x + 1; }
    }
    static final class MinusOne implements Op {
        public int apply(int x) { return x - 1; }
    }
    static int add(int a, int b) { return a + b; }
    static int dispatch(Op op, int x) { return op.apply(x); }
    static void plainWork() { while (plainRunning) {} }
    static void volatileWork() { while (volatileRunning) {} }

    private static void hot() {
        Op first = new PlusOne();
        long sum = 0;
        for (int i = 0; i < 2_000_000; i++) sum += dispatch(first, i);
        Op second = new MinusOne();
        int changed = dispatch(second, 10);
        if (sum != 2_000_001_000_000L || changed != 9) {
            throw new AssertionError("incorrect result");
        }
        System.out.println("sum=" + sum + ", changed=" + changed);
    }

    private static void stop(boolean useVolatile) throws InterruptedException {
        Thread worker = new Thread(useVolatile ? JitLab::volatileWork : JitLab::plainWork);
        worker.setDaemon(true); // A racy infinite loop must not retain this process.
        worker.start();
        Thread.sleep(1000); // Scheduling aid, not memory synchronization.
        if (useVolatile) volatileRunning = false;
        else plainRunning = false;
        worker.join(1000);
        System.out.println("mode=" + (useVolatile ? "volatile" : "plain")
                + ", workerAlive=" + worker.isAlive());
    }

    private static void counter() throws InterruptedException {
        CyclicBarrier bothRead = new CyclicBarrier(2);
        AtomicInteger failures = new AtomicInteger();
        Runnable racyIncrement = () -> {
            int old = count;
            try {
                bothRead.await(5, java.util.concurrent.TimeUnit.SECONDS);
                count = old + 1;
            } catch (Exception e) {
                failures.incrementAndGet();
            }
        };
        Thread a = new Thread(racyIncrement), b = new Thread(racyIncrement);
        a.start(); b.start(); a.join(); b.join();
        if (failures.get() != 0 || count != 1) throw new AssertionError("counter setup failed");
        AtomicInteger atomic = new AtomicInteger();
        Thread c = new Thread(atomic::incrementAndGet), d = new Thread(atomic::incrementAndGet);
        c.start(); d.start(); c.join(); d.join();
        if (atomic.get() != 2) throw new AssertionError("atomic counter failed");
        System.out.println("volatileSplitIncrement=" + count + ", atomic=" + atomic.get());
    }

    private static void publish() throws InterruptedException {
        AtomicInteger observed = new AtomicInteger(-1);
        Thread reader = new Thread(() -> {
            while (!ready) {} // Intentionally a short one-shot teaching spin.
            observed.set(data);
        });
        reader.setDaemon(true);
        reader.start();
        data = 42;
        ready = true;
        reader.join(2000);
        if (reader.isAlive() || observed.get() != 42) throw new AssertionError("publish check failed");
        System.out.println("published=" + observed.get());
    }

    public static void main(String[] args) throws InterruptedException {
        String mode = args.length == 0 ? "hot" : args[0];
        switch (mode) {
            case "hot": hot(); break;
            case "plain-stop": stop(false); break;
            case "volatile-stop": stop(true); break;
            case "counter": counter(); break;
            case "publish": publish(); break;
            default: throw new IllegalArgumentException("unknown mode: " + mode);
        }
    }
}
