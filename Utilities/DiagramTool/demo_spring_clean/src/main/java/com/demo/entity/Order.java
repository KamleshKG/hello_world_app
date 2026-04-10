package com.demo.entity;
import javax.persistence.*;
import java.time.LocalDateTime;
import java.util.List;
import java.math.BigDecimal;

@Entity
@Table(name = "orders")
public class Order {
    @Id @GeneratedValue(strategy = GenerationType.IDENTITY)
    public Long id;
    @ManyToOne
    @JoinColumn(name = "customer_id", nullable = false)
    private User customer;
    @OneToMany(mappedBy = "order", cascade = CascadeType.ALL)
    private List<OrderItem> items;
    @Enumerated(EnumType.STRING)
    public OrderStatus status;
    private LocalDateTime placedAt;
    @OneToOne(mappedBy = "order", cascade = CascadeType.ALL)
    private Payment payment;
    public BigDecimal getTotal() { return BigDecimal.ZERO; }
}
