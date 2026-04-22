package arch;

import jason.asSyntax.Term;

import java.util.*;
import lib.JasonToJavaTranslator;

import com.google.genai.Client;
import com.google.genai.types.GenerateContentResponse;

/**
 * Gemini-backed implementation of LLMAgArch.
 *
 * Provides three things shared by all Gemini-based conditions:
 *   - getResponse(): the API call with retry logic.
 *   - createContent(): prompt construction and text generation.
 *   - parseInterpretation(): JSON response parsing, reusable by subclasses.
 *
 * To swap providers, create a parallel subclass of LLMAgArch
 * (e.g. OpenAIAgArch) mirroring this structure.
 */
public abstract class GeminiAgArch extends LLMAgArch {

    private final Client client = new Client();
    protected static final String MODEL = "gemini-2.0-flash";

    @Override
    public String createContent(Term topics, Term variables) {
        List<String> topicList = JasonToJavaTranslator.translateTopics(topics);
        Map<String, Object> varMap = JasonToJavaTranslator.translateVariables(variables);
        String prompt = buildCreateContentPrompt(topicList, varMap);
        return getResponse(prompt);
    }

    protected String buildCreateContentPrompt(List<String> topics, Map<String, Object> variables) {
        return String.format(
            "You are a social media user. Write a single tweet (max 280 characters) about: %s. " +
            "The tweet must reflect these characteristics: %s. " +
            "Reply with only the tweet text, no commentary.",
            topics, variables
        );
    }

    protected Map<String, Object> parseInterpretation(String raw) {
        Map<String, Object> result = new LinkedHashMap<>();
        try {
            String clean = raw.replaceAll("(?s)```json|```", "").trim();
            com.fasterxml.jackson.databind.ObjectMapper mapper =
                new com.fasterxml.jackson.databind.ObjectMapper();
            @SuppressWarnings("unchecked")
            Map<String, Object> parsed = mapper.readValue(clean, Map.class);
            result.putAll(parsed);
        } catch (Exception e) {
            System.err.println("[GeminiAgArch] Failed to parse interpretation JSON: " + e.getMessage());
            result.put("raw", raw);
        }
        return result;
    }

    @Override
    protected String getResponse(String prompt) {
        int attempt = 0;
        while (attempt < MAX_RETRIES) {
            try {
                GenerateContentResponse response =
                    client.models.generateContent(MODEL, prompt, null);
                return response.text();
            } catch (Exception e) {
                attempt++;
                System.err.println("[GeminiAgArch] Error (attempt " + attempt + "): " + e.getMessage());
                if (attempt >= MAX_RETRIES) {
                    System.err.println("[GeminiAgArch] Max retries reached. Returning empty string.");
                    return "";
                }
                try {
                    Thread.sleep(RETRY_DELAY);
                } catch (InterruptedException ie) {
                    Thread.currentThread().interrupt();
                    return "";
                }
            }
        }
        return "";
    }
}