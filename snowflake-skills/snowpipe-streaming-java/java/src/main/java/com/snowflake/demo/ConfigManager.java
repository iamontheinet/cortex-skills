package com.snowflake.demo;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.FileInputStream;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Map;
import java.util.Properties;

public class ConfigManager {
    private final Properties config;
    private final Map<String, Object> profile;

    @SuppressWarnings("unchecked")
    public ConfigManager(String configPath, String profilePath) throws IOException {
        this.config = new Properties();
        try (FileInputStream fis = new FileInputStream(configPath)) {
            config.load(fis);
        }
        ObjectMapper mapper = new ObjectMapper();
        this.profile = mapper.readValue(Files.readString(Path.of(profilePath)), Map.class);
    }

    public String getConfigProperty(String key) {
        return config.getProperty(key);
    }

    public int getConfigInt(String key, int defaultValue) {
        String val = config.getProperty(key);
        return val != null ? Integer.parseInt(val) : defaultValue;
    }

    public String getProfileProperty(String key) {
        Object val = profile.get(key);
        return val != null ? val.toString() : null;
    }

    public String getUser() { return getProfileProperty("user"); }
    public String getAccount() { return getProfileProperty("account"); }
    public String getUrl() { return getProfileProperty("url"); }
    public String getRole() { return getProfileProperty("role"); }
    public String getDatabase() { return getProfileProperty("database"); }
    public String getSchema() { return getProfileProperty("schema"); }
    public String getWarehouse() { return getProfileProperty("warehouse"); }

    public String getPrivateKeyContent() throws IOException {
        String keyFile = getProfileProperty("private_key_file");
        if (keyFile != null) {
            return Files.readString(Path.of(keyFile));
        }
        return getProfileProperty("private_key");
    }

    public Properties toStreamingProperties() throws IOException {
        Properties props = new Properties();
        props.put("user", getUser());
        props.put("account", getAccount());
        props.put("url", getUrl());
        props.put("role", getRole());
        props.put("private_key", getPrivateKeyContent());
        return props;
    }
}
