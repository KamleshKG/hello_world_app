package com.demo.entity;
import javax.persistence.*;
import java.math.BigDecimal;
import java.time.LocalDateTime;

@Entity
@Table(name = "payments")
public class Payment {
    @Id @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    @OneToOne
    @JoinColumn(name = "order_id")
    private Order order;
    private BigDecimal amount;
    private String transactionId;
    private String gateway;
    @Enumerated(EnumType.STRING)
    public PaymentStatus status;
    private LocalDateTime paidAt;
}
