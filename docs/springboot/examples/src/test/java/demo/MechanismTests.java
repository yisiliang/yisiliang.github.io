package demo;
import java.time.Duration;
import java.util.concurrent.atomic.AtomicBoolean;
import org.junit.jupiter.api.Test;
import static org.assertj.core.api.Assertions.*;
import org.springframework.boot.ApplicationRunner;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.WebApplicationType;
import org.springframework.boot.autoconfigure.AutoConfiguration;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.boot.autoconfigure.AutoConfigurations;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
class MechanismTests {
 private final ApplicationContextRunner binder=new ApplicationContextRunner()
  .withUserConfiguration(PropertiesConfiguration.class)
  .withPropertyValues("demo.message=test","demo.timeout=3s","demo.retries=2");
 @Test void durationBinding() {
  binder.run(c->{ assertThat(c).hasNotFailed(); assertThat(c.getBean(DemoProperties.class).timeout()).isEqualTo(Duration.ofSeconds(3)); });
 }
 @Test void invalidDurationFails() { binder.withPropertyValues("demo.timeout=abc").run(c->assertThat(c).hasFailed()); }
 @Test void constraintFailureStopsCreation() { binder.withPropertyValues("demo.retries=0").run(c->assertThat(c).hasFailed()); }
 @Test void missingBeanDefaultAndBackoff() {
  new ApplicationContextRunner().withConfiguration(AutoConfigurations.of(DefaultConfiguration.class))
   .run(c->assertThat(c.getBean(Greeting.class).text()).isEqualTo("default"));
  new ApplicationContextRunner().withConfiguration(AutoConfigurations.of(DefaultConfiguration.class)).withUserConfiguration(UserConfiguration.class)
   .run(c->{ assertThat(c).doesNotHaveBean("defaultGreeting"); assertThat(c.getBean(Greeting.class).text()).isEqualTo("user"); });
 }
 @Test void propertyConditionUsesExplicitValue() {
  new ApplicationContextRunner().withUserConfiguration(SwitchConfiguration.class).run(c->assertThat(c).doesNotHaveBean("switched"));
  for(String value:new String[]{"false","abc"}) new ApplicationContextRunner().withUserConfiguration(SwitchConfiguration.class)
   .withPropertyValues("demo.enabled="+value).run(c->assertThat(c).doesNotHaveBean("switched"));
  new ApplicationContextRunner().withUserConfiguration(SwitchConfiguration.class).withPropertyValues("demo.enabled=TRUE").run(c->assertThat(c).hasBean("switched"));
 }
 @Test void commandLineBeatsConfigAndReadyFollowsRunner() {
  AtomicBoolean called=new AtomicBoolean(),ready=new AtomicBoolean(); SpringApplication app=app(RunnerConfiguration.class,called);
  app.addListeners(e->{if(e instanceof ApplicationReadyEvent)ready.set(called.get());});
  try(var c=app.run("--demo.message=cli","--spring.main.banner-mode=off")) {
   assertThat(c.getEnvironment().getProperty("demo.message")).isEqualTo("cli");assertThat(ready).isTrue();
  }
 }
 @Test void runnerFailurePreventsReady() {
  AtomicBoolean ready=new AtomicBoolean(); SpringApplication app=app(FailingRunnerConfiguration.class,new AtomicBoolean());
  app.addListeners(e->{if(e instanceof ApplicationReadyEvent)ready.set(true);});
  assertThatThrownBy(()->app.run("--spring.main.banner-mode=off")).isInstanceOf(IllegalStateException.class).hasMessage("teaching failure"); assertThat(ready).isFalse();
 }
 @Test void profileConfigAppliedBeforeRunner() {
  try(var c=app(RunnerConfiguration.class,new AtomicBoolean()).run("--spring.profiles.active=dev","--spring.main.banner-mode=off"))
   {assertThat(c.getEnvironment().getProperty("demo.message")).isEqualTo("dev");}
 }
 @Test void optionalMissingConfigPermitsStart() {
  try(var c=app(RunnerConfiguration.class,new AtomicBoolean()).run("--spring.config.import=optional:classpath:not-present-learning.properties","--spring.main.banner-mode=off"))
   {assertThat(c.isActive()).isTrue();}
 }
 static SpringApplication app(Class<?> source,AtomicBoolean called) {
  SpringApplication app=new SpringApplication(source);app.setWebApplicationType(WebApplicationType.NONE);
  app.addInitializers(c->c.getBeanFactory().registerSingleton("runnerCalled",called));return app;
 }
 @Configuration(proxyBeanMethods=false) @EnableConfigurationProperties(DemoProperties.class) static class PropertiesConfiguration {}
 record Greeting(String text) {}
 @AutoConfiguration static class DefaultConfiguration {
  @Bean @ConditionalOnMissingBean(Greeting.class) Greeting defaultGreeting(){return new Greeting("default");}
 }
 @Configuration(proxyBeanMethods=false) static class UserConfiguration { @Bean Greeting userGreeting(){return new Greeting("user");} }
 @Configuration(proxyBeanMethods=false) static class SwitchConfiguration {
  @Bean @ConditionalOnProperty(prefix="demo",name="enabled",havingValue="true") String switched(){return "on";}
 }
 @Configuration(proxyBeanMethods=false) static class RunnerConfiguration {
  @Bean ApplicationRunner runner(AtomicBoolean called){return args->called.set(true);}
 }
 @Configuration(proxyBeanMethods=false) static class FailingRunnerConfiguration {
  @Bean ApplicationRunner runner(){return args->{throw new IllegalStateException("teaching failure");};}
 }
}
