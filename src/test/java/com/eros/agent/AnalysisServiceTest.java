package com.eros.agent;

import com.eros.agent.analysis.AnalysisRequest;
import com.eros.agent.analysis.AnalysisResult;
import com.eros.agent.analysis.AnalysisService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import static org.junit.jupiter.api.Assertions.*;

@SpringBootTest
public class AnalysisServiceTest {

    @Autowired
    private AnalysisService analysisService;

    @Test
    public void testSqlInjectionDetection() {
        AnalysisRequest request = new AnalysisRequest();
        request.setCode("def get_user(user_id): return db.execute(f\"SELECT * FROM users WHERE id={user_id}\")");
        request.setLanguage("python");

        AnalysisResult result = analysisService.analyze(request.getCode(), request.getLanguage());

        assertEquals("completed", result.getStatus());
        assertTrue(result.getRisk_level().equals("CRITICAL") || result.getRisk_level().equals("HIGH"));
        assertFalse(result.getFindings().isEmpty());
    }

    @Test
    public void testCleanCode() {
        AnalysisRequest request = new AnalysisRequest();
        request.setCode("def get_user(user_id: int):\n    query = \"SELECT * FROM users WHERE id = %s\"\n    return db.execute(query, (user_id,))");
        request.setLanguage("python");

        AnalysisResult result = analysisService.analyze(request.getCode(), request.getLanguage());

        assertEquals("completed", result.getStatus());
        assertTrue(result.getFindings().isEmpty());
    }

    @Test
    public void testEmptyCode() {
        AnalysisResult result = analysisService.analyze("", "python");
        assertEquals("completed", result.getStatus());
        assertFalse(result.getFindings().isEmpty());
    }
}
