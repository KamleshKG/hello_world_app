package com.demo.service;
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
