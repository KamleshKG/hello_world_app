package com.demo.service;
import com.demo.entity.*;
import com.demo.repository.PaymentRepository;
import com.demo.feign.PaymentGatewayClient;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.kafka.core.KafkaTemplate;

@Service
public class PaymentService {
    @Autowired private PaymentRepository    paymentRepository;
    @Autowired private PaymentGatewayClient paymentGatewayClient;
    @Autowired private KafkaTemplate<String, String> kafkaTemplate;

    @Transactional
    public Payment processPayment(Order order, String token) {
        String txnId = paymentGatewayClient.charge(order.getTotal(), token);
        Payment p    = new Payment();
        p.order         = order;
        p.transactionId = txnId;
        p.status        = PaymentStatus.PAID;
        Payment saved   = paymentRepository.save(p);
        kafkaTemplate.send("payment-events", "PAID:" + txnId);
        return saved;
    }

    public boolean refund(String transactionId) {
        return paymentGatewayClient.refund(transactionId);
    }
}
