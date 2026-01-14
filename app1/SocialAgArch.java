import jason.asSyntax.*;
import jason.architecture.*;
import jason.asSemantics.ActionExec;
import jason.asSyntax.ASSyntax;

import java.io.*;
import java.net.*;
import org.json.*;

import java.util.*;

public class SocialAgArch extends AgArch {

    @Override
    public void act(ActionExec action) {
        String afunctor = action.getActionTerm().getFunctor();
        if (afunctor.equals("createPost")) {
            Term topics = action.getActionTerm().getTerm(0);
            Term variables = action.getActionTerm().getTerm(1);
            action.setResult(createPost(translateTopics(topics), translateVariables(variables)));
        } else {
            // esto llama al environment ¿?
            super.act(action);
        }
    }

    private List<String> translateTopics(Term t){
        String topics = t.toString();
        topics = topics.trim().substring(1, topics.length() - 1);
        String[] items = topics.split("\\s*,\\s*");
        List<String> list = new ArrayList<>();
        for (String topic : items) {
            list.add(topic);
        }
        return list;
    }

    //TODO: allow different value types
    private Map<String, String> translateVariables(Term v){
        String variables = v.toString();
        variables = variables.trim().substring(1, variables.length() - 1);
        String[] items = variables.split("\\s*,\\s*");
        Map<String, String> map = new HashMap<>();
        for (String item : items) {
            // Assuming format is always key(value)
            int openParen = item.indexOf('(');
            int closeParen = item.lastIndexOf(')');
            String key = item.substring(0, openParen);
            String value = item.substring(openParen + 1, closeParen);
            map.put(key, value);
        }
        return map;
    }

    //TODO: How do I send this to the ENV???
    private boolean createPost(List<String> topics, Map<String, String> variables) {
        try {
            // 1. Build the prompt
            StringBuilder promptBuilder = new StringBuilder("Write a social media post about:\n");
            for (String topic : topics) {
                promptBuilder.append("- ").append(topic).append("\n");
            }
            promptBuilder.append("Include the following details:\n");
            for (Map.Entry<String, String> entry : variables.entrySet()) {
                promptBuilder.append(entry.getKey()).append(": ").append(entry.getValue()).append("\n");
            }
            String prompt = promptBuilder.toString();

            System.out.print(prompt);

            // 2. Prepare the HTTP connection to the free mlvoca.com LLM API
            URL url = new URL("https://mlvoca.com/api/generate");
            HttpURLConnection conn = (HttpURLConnection) url.openConnection();
            conn.setRequestMethod("POST");
            conn.setRequestProperty("Content-Type", "application/json");
            conn.setDoOutput(true);

            // JSON body: choose the free "deepseek-r1:1.5b" model
            JSONObject body = new JSONObject();
            body.put("model", "deepseek-r1:1.5b");
            body.put("prompt", prompt);
            body.put("stream", false); // single complete response

            try (OutputStream os = conn.getOutputStream()) {
                byte[] input = body.toString().getBytes("utf-8");
                os.write(input, 0, input.length);
            }

            // 3. Read the response
            StringBuilder responseBuilder = new StringBuilder();
            try (BufferedReader br = new BufferedReader(new InputStreamReader(conn.getInputStream(), "utf-8"))) {
                String line;
                while ((line = br.readLine()) != null) {
                    responseBuilder.append(line);
                }
            }

            JSONObject jsonResponse = new JSONObject(responseBuilder.toString());
            // The API returns the generated text in "response"
            String generatedText = jsonResponse.optString("response");

            // 4. Use the generated text (print/log or send to the Jason agent)
            System.out.println("Generated post:\n" + generatedText);

            return true;
        } catch (Exception e) {
            e.printStackTrace();
            return false;
        }
    }
}

//updateFeed es perceive
//searchContent es perceive
//searchAuthor es perceive
//createPost es act
