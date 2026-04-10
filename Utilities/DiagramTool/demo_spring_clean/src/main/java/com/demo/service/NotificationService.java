package com.demo.service;
import com.demo.entity.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.scheduling.annotation.Async;
import org.springframework.kafka.core.KafkaTemplate;

@Service
public class NotificationService {
    @Autowired
    private KafkaTemplate<String, String> kafkaTemplate;

    @Async
    public void notifyOrderPlaced(Order order) {
        kafkaTemplate.send("notifications", "ORDER_CONFIRMED:" + order.id);
    }

    @Async
    public void sendWelcomeEmail(User user) {
        kafkaTemplate.send("notifications", "WELCOME:" + user.email);
    }

    @Async
    public void notifyShipped(Order order, String trackingId) {
        kafkaTemplate.send("notifications", "SHIPPED:" + order.id + ":" + trackingId);
    }
}
