package cn.yinling.guide;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.*;
import jakarta.servlet.http.*;
@Configuration
public class PreviewCacheConfig implements WebMvcConfigurer {
 @Override public void addInterceptors(InterceptorRegistry registry){
  registry.addInterceptor(new org.springframework.web.servlet.HandlerInterceptor(){
   @Override public boolean preHandle(HttpServletRequest request,HttpServletResponse response,Object handler){response.setHeader("Cache-Control","no-store, max-age=0");return true;}
  });
 }
}
