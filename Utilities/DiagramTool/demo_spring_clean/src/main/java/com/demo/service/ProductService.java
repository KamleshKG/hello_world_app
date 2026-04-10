package com.demo.service;
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
