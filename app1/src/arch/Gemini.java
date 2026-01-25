package arch;

import lib.Translator;

import java.util.*;


import jason.asSyntax.Term;

import com.google.genai.Client;
import com.google.genai.types.GenerateContentResponse;

public final class Gemini {

    private static final Client client = new Client();
    private static final String model = "gemini-3-flash-preview";

    // ---------------- PUBLIC API ----------------

    public static String createContent(Term t, Term v) {
        List<String> topics = Translator.translateTopics(t);
        Map<String, String> variables = Translator.translateVariables(v);
        String prompt = String.format("Create a tweet that talks about %s and has the following characteristics: %s", topics.toString(), variables.toString());
        System.out.print(prompt);
        return getResponse(prompt);
    }

    public static String createContent(
            Term interpretations,
            Term originalContent,
            Term topics,
            Term variables) {

       return "blabla0;";
    }

    private static String getResponse(String prompt) {
        GenerateContentResponse response = client.models.generateContent(model, prompt, null);
        System.out.print(response.text());
        return response.text();
    }
}
