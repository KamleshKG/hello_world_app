package com.demo.service;
import com.demo.entity.*;
import com.demo.repository.*;
import com.demo.feign.PaymentGatewayClient;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.annotation.KafkaListener;
import java.util.List;

@Service
public class OrderService {
    @Autowired private OrderRepository      orderRepository;
    @Autowired private ProductRepository    productRepository;
    @Autowired private PaymentRepository    paymentRepository;
    @Autowired private ProductService       productService;
    @Autowired private NotificationService  notificationService;
    @Autowired private PaymentGatewayClient paymentGatewayClient;
    @Autowired private KafkaTemplate<String, String> kafkaTemplate;

    @Transactional
    public Order placeOrder(User customer, List<OrderItem> items, String token) {
        Order order = new Order();
        order.customer = customer;
        order.status   = OrderStatus.CONFIRMED;
        Order saved    = orderRepository.save(order);
        kafkaTemplate.send("order-events", "ORDER_PLACED:" + saved.id);
        notificationService.notifyOrderPlaced(saved);
        return saved;
    }

    @Transactional
    public Order ship(Long orderId, String trackingId) {
        Order o = orderRepository.findById(orderId).orElseThrow();
        o.status = OrderStatus.SHIPPED;
        kafkaTemplate.send("order-events", "SHIPPED:" + orderId);
        return orderRepository.save(o);
    }

    @KafkaListener(topics = "payment-events")
    public void onPaymentEvent(String msg) { }

    public List<Order> getCustomerOrders(User customer) {
        return orderRepository.findByCustomer(customer);
    }
}
