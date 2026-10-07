package demo;
import java.time.Duration;
import jakarta.validation.constraints.Min;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.validation.annotation.Validated;
@Validated
@ConfigurationProperties("demo")
public record DemoProperties(String message,Duration timeout,@Min(1) int retries) {}
