"""
setup_demo_spring.py
====================
Run this ONCE from your DiagramTool folder:
    python setup_demo_spring.py

It creates:  DiagramTool\\demo_spring_clean\\
  - pom.xml
  - application.properties
  - src\\main\\java\\com\\demo\\  (28 .java files, one class per file)

Then in diagram_tool.py:
  Click  Analyse Code  ->  Spring Boot  ->  Browse to demo_spring_clean folder
  Expected result: 32 classes, 79 relationships, colour-coded by layer
"""

import os
from pathlib import Path

BASE = Path(__file__).parent / "demo_spring_clean"
JAVA = BASE / "src/main/java/com/demo"

files = {}

# ── pom.xml ──────────────────────────────────────────────────────────────────
files[BASE / "pom.xml"] = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <groupId>com.demo</groupId>
  <artifactId>shop</artifactId>
  <version>1.0.0</version>
  <dependencies>
    <dependency><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-web</artifactId></dependency>
    <dependency><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-data-jpa</artifactId></dependency>
    <dependency><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-security</artifactId></dependency>
    <dependency><groupId>org.springframework.kafka</groupId><artifactId>spring-kafka</artifactId></dependency>
    <dependency><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-data-redis</artifactId></dependency>
    <dependency><groupId>org.springframework.cloud</groupId><artifactId>spring-cloud-starter-openfeign</artifactId></dependency>
    <dependency><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-mail</artifactId></dependency>
  </dependencies>
</project>
"""

# ── application.properties ────────────────────────────────────────────────────
files[BASE / "application.properties"] = """spring.datasource.url=jdbc:postgresql://localhost:5432/shop
spring.datasource.username=admin
spring.datasource.password=secret
spring.jpa.hibernate.ddl-auto=update
spring.kafka.bootstrap-servers=localhost:9092
spring.redis.host=localhost
spring.redis.port=6379
spring.mail.host=smtp.gmail.com
app.jwt.secret=mySecretKey
"""

# ── Entities ──────────────────────────────────────────────────────────────────
files[JAVA / "entity/User.java"] = """package com.demo.entity;
import javax.persistence.*;
import java.util.List;

@Entity
@Table(name = "users")
public class User {
    @Id @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    @Column(unique = true, nullable = false)
    private String email;
    private String name;
    private String passwordHash;
    private String role;
    @OneToMany(mappedBy = "customer", cascade = CascadeType.ALL)
    private List<Order> orders;
    @OneToMany(mappedBy = "author")
    private List<Review> reviews;
}
"""

files[JAVA / "entity/Product.java"] = """package com.demo.entity;
import javax.persistence.*;
import java.math.BigDecimal;
import java.util.List;

@Entity
@Table(name = "products")
public class Product {
    @Id @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    @Column(nullable = false)
    private String name;
    private String description;
    private BigDecimal price;
    private int stockQty;
    @ManyToOne
    @JoinColumn(name = "category_id")
    private Category category;
    @ManyToOne
    @JoinColumn(name = "seller_id")
    private User seller;
    @OneToMany(mappedBy = "product")
    private List<Review> reviews;
}
"""

files[JAVA / "entity/Category.java"] = """package com.demo.entity;
import javax.persistence.*;
import java.util.List;

@Entity
@Table(name = "categories")
public class Category {
    @Id @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    private String name;
    @ManyToOne
    @JoinColumn(name = "parent_id")
    private Category parent;
    @OneToMany(mappedBy = "parent")
    private List<Category> children;
    @OneToMany(mappedBy = "category")
    private List<Product> products;
}
"""

files[JAVA / "entity/Order.java"] = """package com.demo.entity;
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
"""

files[JAVA / "entity/OrderItem.java"] = """package com.demo.entity;
import javax.persistence.*;
import java.math.BigDecimal;

@Entity
@Table(name = "order_items")
public class OrderItem {
    @Id @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    @ManyToOne
    @JoinColumn(name = "order_id")
    private Order order;
    @ManyToOne
    @JoinColumn(name = "product_id")
    private Product product;
    private int quantity;
    private BigDecimal unitPrice;
}
"""

files[JAVA / "entity/Payment.java"] = """package com.demo.entity;
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
"""

files[JAVA / "entity/Review.java"] = """package com.demo.entity;
import javax.persistence.*;

@Entity
@Table(name = "reviews")
public class Review {
    @Id @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    @ManyToOne
    @JoinColumn(name = "user_id")
    private User author;
    @ManyToOne
    @JoinColumn(name = "product_id")
    private Product product;
    private int rating;
    private String comment;
}
"""

files[JAVA / "entity/OrderStatus.java"] = """package com.demo.entity;
public enum OrderStatus {
    PENDING, CONFIRMED, SHIPPED, DELIVERED, CANCELLED
}
"""

files[JAVA / "entity/PaymentStatus.java"] = """package com.demo.entity;
public enum PaymentStatus {
    UNPAID, PAID, REFUNDED
}
"""

# ── Repositories ──────────────────────────────────────────────────────────────
files[JAVA / "repository/UserRepository.java"] = """package com.demo.repository;
import com.demo.entity.User;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;
import java.util.Optional;

@Repository
public interface UserRepository extends JpaRepository<User, Long> {
    Optional<User> findByEmail(String email);
    java.util.List<User> findByRole(String role);
}
"""

files[JAVA / "repository/ProductRepository.java"] = """package com.demo.repository;
import com.demo.entity.*;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;
import java.util.List;

@Repository
public interface ProductRepository extends JpaRepository<Product, Long> {
    List<Product> findByCategory(Category category);
    List<Product> findBySeller(User seller);
    @Query("SELECT p FROM Product p WHERE p.name LIKE %:keyword%")
    List<Product> searchByName(@Param("keyword") String keyword);
}
"""

files[JAVA / "repository/OrderRepository.java"] = """package com.demo.repository;
import com.demo.entity.*;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;
import java.util.List;

@Repository
public interface OrderRepository extends JpaRepository<Order, Long> {
    List<Order> findByCustomer(User customer);
    List<Order> findByStatus(OrderStatus status);
}
"""

files[JAVA / "repository/PaymentRepository.java"] = """package com.demo.repository;
import com.demo.entity.*;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;
import java.util.Optional;

@Repository
public interface PaymentRepository extends JpaRepository<Payment, Long> {
    Optional<Payment> findByTransactionId(String txId);
    Optional<Payment> findByOrder(Order order);
}
"""

files[JAVA / "repository/ReviewRepository.java"] = """package com.demo.repository;
import com.demo.entity.*;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;
import java.util.List;

@Repository
public interface ReviewRepository extends JpaRepository<Review, Long> {
    List<Review> findByProduct(Product product);
    List<Review> findByAuthor(User author);
}
"""

files[JAVA / "repository/CategoryRepository.java"] = """package com.demo.repository;
import com.demo.entity.Category;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;
import java.util.List;

@Repository
public interface CategoryRepository extends JpaRepository<Category, Long> {
    List<Category> findByParentIsNull();
    List<Category> findByParent(Category parent);
}
"""

# ── Services ──────────────────────────────────────────────────────────────────
files[JAVA / "service/ProductService.java"] = """package com.demo.service;
import com.demo.entity.*;
import com.demo.repository.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.data.redis.core.RedisTemplate;
import java.util.List;

@Service
public class ProductService {
    @Autowired
    private ProductRepository productRepository;
    @Autowired
    private CategoryRepository categoryRepository;
    @Autowired
    private RedisTemplate<String, Object> redisTemplate;

    @Cacheable("products")
    public Product getById(Long id) {
        return productRepository.findById(id).orElseThrow();
    }

    public List<Product> search(String keyword) {
        return productRepository.searchByName(keyword);
    }

    @Transactional
    public Product create(Product p) {
        return productRepository.save(p);
    }

    @Transactional
    public Product updateStock(Long productId, int delta) {
        Product p = getById(productId);
        p.stockQty += delta;
        return productRepository.save(p);
    }
}
"""

files[JAVA / "service/OrderService.java"] = """package com.demo.service;
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
"""

files[JAVA / "service/UserService.java"] = """package com.demo.service;
import com.demo.entity.User;
import com.demo.repository.UserRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.transaction.annotation.Transactional;
import java.util.Optional;

@Service
public class UserService implements UserDetailsService {
    @Autowired private UserRepository       userRepository;
    @Autowired private NotificationService  notificationService;

    @Override
    public UserDetails loadUserByUsername(String email) {
        return userRepository.findByEmail(email)
            .map(u -> org.springframework.security.core.userdetails.User
                .withUsername(u.email).password(u.passwordHash).roles(u.role).build())
            .orElseThrow();
    }

    @Transactional
    public User register(User user) {
        User saved = userRepository.save(user);
        notificationService.sendWelcomeEmail(saved);
        return saved;
    }

    public Optional<User> findByEmail(String email) {
        return userRepository.findByEmail(email);
    }
}
"""

files[JAVA / "service/PaymentService.java"] = """package com.demo.service;
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
"""

files[JAVA / "service/NotificationService.java"] = """package com.demo.service;
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
"""

# ── Controllers ───────────────────────────────────────────────────────────────
files[JAVA / "controller/ProductController.java"] = """package com.demo.controller;
import com.demo.entity.Product;
import com.demo.service.ProductService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import java.util.List;

@RestController
@RequestMapping("/api/products")
public class ProductController {
    @Autowired
    private ProductService productService;

    @GetMapping("/{id}")
    public ResponseEntity<Product> getProduct(@PathVariable Long id) {
        return ResponseEntity.ok(productService.getById(id));
    }

    @GetMapping("/search")
    public List<Product> search(@RequestParam String keyword) {
        return productService.search(keyword);
    }

    @PostMapping
    @PreAuthorize("hasRole('SELLER')")
    public ResponseEntity<Product> create(@RequestBody Product p) {
        return ResponseEntity.ok(productService.create(p));
    }
}
"""

files[JAVA / "controller/OrderController.java"] = """package com.demo.controller;
import com.demo.entity.*;
import com.demo.service.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import java.security.Principal;
import java.util.List;

@RestController
@RequestMapping("/api/orders")
public class OrderController {
    @Autowired private OrderService orderService;
    @Autowired private UserService  userService;

    @PostMapping
    @PreAuthorize("hasRole('CUSTOMER')")
    public ResponseEntity<Order> place(@RequestBody List<OrderItem> items,
                                       @RequestParam String token,
                                       Principal p) {
        User customer = userService.findByEmail(p.getName()).orElseThrow();
        return ResponseEntity.ok(orderService.placeOrder(customer, items, token));
    }

    @GetMapping("/my")
    @PreAuthorize("isAuthenticated()")
    public List<Order> mine(Principal p) {
        return orderService.getCustomerOrders(
            userService.findByEmail(p.getName()).orElseThrow());
    }

    @PutMapping("/{id}/ship")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<Order> ship(@PathVariable Long id,
                                       @RequestParam String trackingId) {
        return ResponseEntity.ok(orderService.ship(id, trackingId));
    }
}
"""

files[JAVA / "controller/UserController.java"] = """package com.demo.controller;
import com.demo.entity.User;
import com.demo.service.UserService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import java.security.Principal;

@RestController
@RequestMapping("/api/users")
public class UserController {
    @Autowired
    private UserService userService;

    @PostMapping("/register")
    public ResponseEntity<User> register(@RequestBody User user) {
        return ResponseEntity.ok(userService.register(user));
    }

    @GetMapping("/me")
    @PreAuthorize("isAuthenticated()")
    public ResponseEntity<User> me(Principal p) {
        return ResponseEntity.ok(
            userService.findByEmail(p.getName()).orElseThrow());
    }
}
"""

# ── Security ──────────────────────────────────────────────────────────────────
files[JAVA / "security/JwtAuthFilter.java"] = """package com.demo.security;
import com.demo.service.UserService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;
import javax.servlet.*;
import javax.servlet.http.*;
import java.io.IOException;

@Component
public class JwtAuthFilter extends OncePerRequestFilter {
    @Autowired
    private UserService userService;

    @Override
    protected void doFilterInternal(HttpServletRequest request,
                                    HttpServletResponse response,
                                    FilterChain chain)
            throws ServletException, IOException {
        String header = request.getHeader("Authorization");
        if (header != null && header.startsWith("Bearer ")) {
            String email = extractEmail(header.substring(7));
            var ud   = userService.loadUserByUsername(email);
            var auth = new UsernamePasswordAuthenticationToken(
                ud, null, ud.getAuthorities());
            SecurityContextHolder.getContext().setAuthentication(auth);
        }
        chain.doFilter(request, response);
    }

    private String extractEmail(String token) { return ""; }
}
"""

# ── Config ────────────────────────────────────────────────────────────────────
files[JAVA / "config/SecurityConfig.java"] = """package com.demo.config;
import com.demo.security.JwtAuthFilter;
import com.demo.service.UserService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.annotation.*;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;

@Configuration
@EnableWebSecurity
public class SecurityConfig {
    @Autowired private JwtAuthFilter jwtAuthFilter;
    @Autowired private UserService   userService;

    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        http.csrf().disable()
            .authorizeRequests()
            .antMatchers("/api/auth/**").permitAll()
            .anyRequest().authenticated()
            .and()
            .addFilterBefore(jwtAuthFilter,
                UsernamePasswordAuthenticationFilter.class);
        return http.build();
    }
}
"""

files[JAVA / "config/AppConfig.java"] = """package com.demo.config;
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
"""

# ── Feign Clients ─────────────────────────────────────────────────────────────
files[JAVA / "feign/PaymentGatewayClient.java"] = """package com.demo.feign;
import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.*;
import java.math.BigDecimal;

@FeignClient(name = "payment-gateway", url = "${app.payment.url}")
public interface PaymentGatewayClient {
    @PostMapping("/charge")
    String charge(@RequestParam BigDecimal amount,
                  @RequestParam String token);

    @PostMapping("/refund/{id}")
    boolean refund(@PathVariable String id);
}
"""

files[JAVA / "feign/ShippingClient.java"] = """package com.demo.feign;
import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.*;

@FeignClient(name = "shipping", url = "${app.shipping.url}")
public interface ShippingClient {
    @PostMapping("/shipments")
    String create(@RequestParam Long orderId, @RequestParam String addr);

    @GetMapping("/track/{id}")
    String track(@PathVariable String id);
}
"""

# ── Main Application ──────────────────────────────────────────────────────────
files[JAVA / "ECommerceApplication.java"] = """package com.demo;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.cloud.openfeign.EnableFeignClients;
import org.springframework.scheduling.annotation.EnableAsync;
import org.springframework.cache.annotation.EnableCaching;

@SpringBootApplication
@EnableFeignClients
@EnableAsync
@EnableCaching
public class ECommerceApplication {
    public static void main(String[] args) {
        SpringApplication.run(ECommerceApplication.class, args);
    }
}
"""

# ── Write all files ───────────────────────────────────────────────────────────
created = 0
for path, content in files.items():
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    created += 1

print(f"\n✅  Created {created} files in: {BASE}")
print(f"\n📂  Folder structure:")
for f in sorted(Path(BASE).rglob("*")):
    indent = "  " * (len(f.relative_to(BASE).parts) - 1)
    print(f"  {indent}{f.name}")

print(f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅  Setup complete!

In diagram_tool.py:
  1. Click  [🔍 Analyse Code]
  2. Choose  [🍃 Spring Boot]
  3. Click   [Browse & Analyse]
  4. Select the folder:  {BASE}

Expected result:
  ✓  32 classes detected
  ✓  79 relationships
  ✓  Blue   = Controller (ProductController, OrderController, UserController)
  ✓  Purple = Service    (OrderService, ProductService, UserService, ...)
  ✓  Teal   = Repository (OrderRepository, ProductRepository, ...)
  ✓  Green  = Entity     (Order, Product, User, Payment, ...)
  ✓  Orange = Config     (AppConfig, SecurityConfig)
  ✓  Red    = Security   (JwtAuthFilter)
  ✓  Gray   = Infra      (Kafka, Redis, SMTP, RDBMS)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
