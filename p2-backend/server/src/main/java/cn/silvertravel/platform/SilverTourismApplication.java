package cn.silvertravel.platform;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.autoconfigure.security.servlet.UserDetailsServiceAutoConfiguration;

@SpringBootApplication(exclude = UserDetailsServiceAutoConfiguration.class)
public class SilverTourismApplication {

    public static void main(String[] args) {
        SpringApplication.run(SilverTourismApplication.class, args);
    }
}
