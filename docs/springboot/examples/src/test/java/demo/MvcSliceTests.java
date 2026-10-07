package demo;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.test.web.servlet.MockMvc;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;
@WebMvcTest(PingController.class)
class MvcSliceTests {
 @Autowired MockMvc mvc;
 @Test void dispatcherServletRoutesPing() throws Exception {
  mvc.perform(get("/ping")).andExpect(status().isOk()).andExpect(content().string("pong"));
 }
}
