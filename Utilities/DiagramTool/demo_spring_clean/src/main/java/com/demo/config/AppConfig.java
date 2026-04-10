package com.demo.config;
import org.springframework.context.annotation.*;
import org.springframework.cache.annotation.EnableCaching;
import org.springframework.scheduling.annotation.EnableAsync;
import org.springframework.kafka.core.*;
import org.springframework.data.redis.core.RedisTemplate;
import java.util.HashMap;

@Configuration
@EnableCaching
@EnableAsync
public class AppConfig {
    @Bean
    public KafkaTemplate<String, String> kafkaTemplate(
            ProducerFactory<String, String> factory) {
        return new KafkaTemplate<>(factory);
    }

    @Bean
    public RedisTemplate<String, Object> redisTemplate() {
        return new RedisTemplate<>();
    }

    @Bean
    public ProducerFactory<String, String> producerFactory() {
        return new DefaultKafkaProducerFactory<>(new HashMap<>());
    }
}
