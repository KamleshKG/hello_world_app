// demo_java/ECommerceSystem.java
// Complex Java demo for DiagramTool code analysis.
// Shows: interfaces, abstract classes, generics, composition,
//        aggregation, inheritance, constructor injection.

package com.demo.ecommerce;

import java.util.*;
import java.math.BigDecimal;
import java.time.LocalDateTime;

// ── Domain Enums ──────────────────────────────────────────────────────────────

enum OrderStatus { PENDING, CONFIRMED, SHIPPED, DELIVERED, CANCELLED }
enum PaymentStatus { UNPAID, PAID, REFUNDED }
enum UserRole { CUSTOMER, ADMIN, SELLER }

// ── Domain Models ─────────────────────────────────────────────────────────────

class Address {
    private String street;
    private String city;
    private String pincode;
    private String state;
}

class Money {
    private BigDecimal amount;
    private String currency;

    public Money add(Money other) { return new Money(); }
    public Money multiply(int qty) { return new Money(); }
}

class Product {
    private Long id;
    private String name;
    private String description;
    private Money price;
    private int stockQty;
    private Category category;
    private Seller seller;

    public boolean isInStock() { return stockQty > 0; }
    public void reduceStock(int qty) { stockQty -= qty; }
}

class Category {
    private Long id;
    private String name;
    private Category parent;  // self-reference for hierarchy
    private List<Product> products;
}

class User {
    private Long id;
    private String email;
    private String name;
    private UserRole role;
    private Address shippingAddress;
    private List<Order> orders;
}

class Seller extends User {
    private String storeName;
    private List<Product> listings;
    private BankAccount bankAccount;
}

class OrderItem {
    private Product product;
    private int quantity;
    private Money unitPrice;

    public Money subtotal() { return unitPrice.multiply(quantity); }
}

class Order {
    private Long id;
    private User customer;
    private List<OrderItem> items;
    private Address deliveryAddress;
    private OrderStatus status;
    private PaymentStatus paymentStatus;
    private LocalDateTime placedAt;
    private Payment payment;

    public Money total() {
        return items.stream()
                    .map(OrderItem::subtotal)
                    .reduce(new Money(), Money::add);
    }
}

class Payment {
    private Long id;
    private Order order;
    private Money amount;
    private String transactionId;
    private PaymentStatus status;
    private LocalDateTime paidAt;
}

class BankAccount {
    private String accountNumber;
    private String ifsc;
    private String holderName;
}

class Cart {
    private User user;
    private List<OrderItem> items;

    public void addItem(Product product, int qty) {}
    public void removeItem(Long productId) {}
    public Money total() { return new Money(); }
}

class Review {
    private User author;
    private Product product;
    private int rating;
    private String comment;
}

// ── Repository Interfaces ─────────────────────────────────────────────────────

interface Repository<T, ID> {
    Optional<T> findById(ID id);
    List<T> findAll();
    T save(T entity);
    void deleteById(ID id);
}

interface ProductRepository extends Repository<Product, Long> {
    List<Product> findByCategory(Category category);
    List<Product> findBySeller(Seller seller);
    List<Product> searchByName(String keyword);
}

interface OrderRepository extends Repository<Order, Long> {
    List<Order> findByCustomer(User customer);
    List<Order> findByStatus(OrderStatus status);
}

interface UserRepository extends Repository<User, Long> {
    Optional<User> findByEmail(String email);
}

interface PaymentRepository extends Repository<Payment, Long> {
    Optional<Payment> findByTransactionId(String txId);
}

// ── Repository Implementations ────────────────────────────────────────────────

abstract class BaseJpaRepository<T, ID> implements Repository<T, ID> {
    protected String tableName;

    @Override
    public List<T> findAll() { return Collections.emptyList(); }

    @Override
    public void deleteById(ID id) {}
}

class ProductRepositoryImpl extends BaseJpaRepository<Product, Long>
        implements ProductRepository {

    public ProductRepositoryImpl() { this.tableName = "products"; }

    @Override
    public Optional<Product> findById(Long id) { return Optional.empty(); }

    @Override
    public Product save(Product product) { return product; }

    @Override
    public List<Product> findByCategory(Category category) { return Collections.emptyList(); }

    @Override
    public List<Product> findBySeller(Seller seller) { return Collections.emptyList(); }

    @Override
    public List<Product> searchByName(String keyword) { return Collections.emptyList(); }
}

class OrderRepositoryImpl extends BaseJpaRepository<Order, Long>
        implements OrderRepository {

    @Override
    public Optional<Order> findById(Long id) { return Optional.empty(); }

    @Override
    public Order save(Order order) { return order; }

    @Override
    public List<Order> findByCustomer(User customer) { return Collections.emptyList(); }

    @Override
    public List<Order> findByStatus(OrderStatus status) { return Collections.emptyList(); }
}

// ── Payment Gateway Interface & Implementations ───────────────────────────────

interface PaymentGateway {
    String charge(Money amount, String token);
    boolean refund(String transactionId);
    boolean verify(String transactionId);
}

class RazorpayGateway implements PaymentGateway {
    private String apiKey;
    private String apiSecret;

    public RazorpayGateway(String apiKey, String apiSecret) {
        this.apiKey    = apiKey;
        this.apiSecret = apiSecret;
    }

    @Override
    public String charge(Money amount, String token) { return "rzp_txn_123"; }

    @Override
    public boolean refund(String transactionId) { return true; }

    @Override
    public boolean verify(String transactionId) { return true; }
}

class StripeGateway implements PaymentGateway {
    private String secretKey;

    public StripeGateway(String secretKey) { this.secretKey = secretKey; }

    @Override
    public String charge(Money amount, String token) { return "stripe_txn_456"; }

    @Override
    public boolean refund(String transactionId) { return true; }

    @Override
    public boolean verify(String transactionId) { return true; }
}

// ── Notification Interface & Implementations ──────────────────────────────────

interface NotificationService {
    void notifyOrderConfirmed(Order order);
    void notifyOrderShipped(Order order, String trackingId);
    void notifyPaymentReceived(Payment payment);
}

class EmailNotificationService implements NotificationService {
    private String smtpHost;

    public EmailNotificationService(String smtpHost) { this.smtpHost = smtpHost; }

    @Override
    public void notifyOrderConfirmed(Order order) {}

    @Override
    public void notifyOrderShipped(Order order, String trackingId) {}

    @Override
    public void notifyPaymentReceived(Payment payment) {}
}

class SMSNotificationService implements NotificationService {
    @Override
    public void notifyOrderConfirmed(Order order) {}

    @Override
    public void notifyOrderShipped(Order order, String trackingId) {}

    @Override
    public void notifyPaymentReceived(Payment payment) {}
}

// ── Pricing Engine ────────────────────────────────────────────────────────────

interface PricingStrategy {
    Money calculatePrice(Product product, User customer, int qty);
}

class StandardPricing implements PricingStrategy {
    @Override
    public Money calculatePrice(Product product, User customer, int qty) {
        return product.price.multiply(qty);
    }
}

class BulkDiscountPricing implements PricingStrategy {
    private int discountThreshold;
    private double discountRate;

    public BulkDiscountPricing(int discountThreshold, double discountRate) {
        this.discountThreshold = discountThreshold;
        this.discountRate      = discountRate;
    }

    @Override
    public Money calculatePrice(Product product, User customer, int qty) {
        if (qty >= discountThreshold) {
            return product.price.multiply((int)(qty * (1 - discountRate)));
        }
        return product.price.multiply(qty);
    }
}

// ── Service Layer ─────────────────────────────────────────────────────────────

class ProductService {
    private ProductRepository productRepository;
    private NotificationService notificationService;

    public ProductService(ProductRepository productRepository,
                          NotificationService notificationService) {
        this.productRepository   = productRepository;
        this.notificationService = notificationService;
    }

    public Product getProduct(Long id) {
        return productRepository.findById(id)
                                .orElseThrow(() -> new RuntimeException("Not found"));
    }

    public List<Product> search(String keyword) {
        return productRepository.searchByName(keyword);
    }

    public Product createProduct(Product product) {
        return productRepository.save(product);
    }
}

class OrderService {
    private OrderRepository     orderRepository;
    private ProductRepository   productRepository;
    private PaymentGateway      paymentGateway;
    private PaymentRepository   paymentRepository;
    private NotificationService notificationService;
    private PricingStrategy     pricingStrategy;

    public OrderService(OrderRepository orderRepository,
                        ProductRepository productRepository,
                        PaymentGateway paymentGateway,
                        PaymentRepository paymentRepository,
                        NotificationService notificationService,
                        PricingStrategy pricingStrategy) {
        this.orderRepository     = orderRepository;
        this.productRepository   = productRepository;
        this.paymentGateway      = paymentGateway;
        this.paymentRepository   = paymentRepository;
        this.notificationService = notificationService;
        this.pricingStrategy     = pricingStrategy;
    }

    public Order placeOrder(Cart cart, User customer, String paymentToken) {
        Order order = new Order();
        String txnId = paymentGateway.charge(cart.total(), paymentToken);
        notificationService.notifyOrderConfirmed(order);
        return orderRepository.save(order);
    }

    public void shipOrder(Long orderId, String trackingId) {
        Order order = orderRepository.findById(orderId)
                                     .orElseThrow(() -> new RuntimeException("Not found"));
        order.status = OrderStatus.SHIPPED;
        orderRepository.save(order);
        notificationService.notifyOrderShipped(order, trackingId);
    }

    public List<Order> getCustomerOrders(User customer) {
        return orderRepository.findByCustomer(customer);
    }
}

class UserService {
    private UserRepository userRepository;

    public UserService(UserRepository userRepository) {
        this.userRepository = userRepository;
    }

    public Optional<User> findByEmail(String email) {
        return userRepository.findByEmail(email);
    }

    public User register(User user) {
        return userRepository.save(user);
    }
}

// ── Application Entry Point ───────────────────────────────────────────────────

class ECommerceApplication {
    public static void main(String[] args) {
        // Wire up dependencies (in real app Spring DI would handle this)
        ProductRepository   productRepo   = new ProductRepositoryImpl();
        OrderRepository     orderRepo     = new OrderRepositoryImpl();
        PaymentGateway      gateway       = new RazorpayGateway("key","secret");
        NotificationService notifier      = new EmailNotificationService("smtp.gmail.com");
        PricingStrategy     pricing       = new BulkDiscountPricing(10, 0.1);

        ProductService productService = new ProductService(productRepo, notifier);
        OrderService   orderService   = new OrderService(
                orderRepo, productRepo, gateway, null, notifier, pricing);

        System.out.println("E-Commerce system started.");
    }
}
