package com.demo.controller;
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
