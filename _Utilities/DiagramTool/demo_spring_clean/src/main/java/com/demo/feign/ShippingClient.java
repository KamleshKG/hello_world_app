package com.demo.feign;
import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.*;

@FeignClient(name = "shipping", url = "${app.shipping.url}")
public interface ShippingClient {
    @PostMapping("/shipments")
    String create(@RequestParam Long orderId, @RequestParam String addr);

    @GetMapping("/track/{id}")
    String track(@PathVariable String id);
}
