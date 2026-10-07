package demo;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.core.env.ConfigurableEnvironment;
import org.springframework.core.env.Environment;
import org.springframework.stereotype.Component;
@Component
public class InspectRunner implements ApplicationRunner {
 private final Environment env;
 private final DemoProperties demo;
 public InspectRunner(Environment env, DemoProperties demo) { this.env=env; this.demo=demo; }
 @Override public void run(ApplicationArguments args) {
  System.out.println("MESSAGE="+demo.message()+" TIMEOUT="+demo.timeout());
  if(env instanceof ConfigurableEnvironment configurable)
   configurable.getPropertySources().forEach(source->System.out.println("SOURCE="+source.getName()));
 }
}
