package com.demo.feign;
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
