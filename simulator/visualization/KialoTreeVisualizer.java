package visualization;

import com.sun.net.httpserver.HttpServer;
import com.sun.net.httpserver.HttpExchange;

import env.ContentManager;
import env.VisualMessage;

import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.concurrent.Executors;

/**
 * Kialo-style debate tree visualizer.
 *
 * Starts an embedded HTTP server on localhost:8765 with two endpoints:
 *   GET /messages  → JSON snapshot of all messages (used by the HTML frontend)
 *   GET /          → redirects to the visualization HTML (optional)
 *
 * The HTML file (visualization/kialo_tree.html) polls /messages every 2s
 * and re-renders the tree, color-coding nodes by relation:
 *   root  → neutral (white/grey)
 *   pro   → green  (relation == 1)
 *   con   → red    (relation == -1)
 *
 * Usage in Env.java:
 *   private final Visualizer visualizer = new KialoTreeVisualizer(contentManager);
 */
public class KialoTreeVisualizer implements Visualizer {

    private static final int PORT = 8765;

    private final ContentManager contentManager;
    private HttpServer server;

    public KialoTreeVisualizer(ContentManager contentManager) {
        this.contentManager = contentManager;
    }

    // ------------------------------------------------------------------ //
    //  Lifecycle
    // ------------------------------------------------------------------ //

    @Override
    public void start() {
        try {
            server = HttpServer.create(new InetSocketAddress("localhost", PORT), 0);
            server.createContext("/messages", this::handleMessages);
            server.createContext("/health",   this::handleHealth);
            server.setExecutor(Executors.newSingleThreadExecutor());
            server.start();
            System.out.println("[KialoTreeVisualizer] HTTP server started → http://localhost:" + PORT + "/messages");
        } catch (IOException e) {
            System.err.println("[KialoTreeVisualizer] Failed to start HTTP server: " + e.getMessage());
        }
    }

    @Override
    public void onUpdate() {
        // Stateless: the HTML frontend polls /messages, nothing to push.
        // If you later switch to WebSockets, broadcast here.
    }

    @Override
    public void stop() {
        if (server != null) {
            server.stop(0);
            System.out.println("[KialoTreeVisualizer] HTTP server stopped.");
        }
    }

    // ------------------------------------------------------------------ //
    //  HTTP handlers
    // ------------------------------------------------------------------ //

    private void handleMessages(HttpExchange exchange) throws IOException {
        if (!"GET".equalsIgnoreCase(exchange.getRequestMethod())) {
            exchange.sendResponseHeaders(405, -1);
            return;
        }

        String json = buildJson();
        byte[] bytes = json.getBytes(StandardCharsets.UTF_8);

        exchange.getResponseHeaders().add("Content-Type", "application/json; charset=utf-8");
        exchange.getResponseHeaders().add("Access-Control-Allow-Origin", "*"); // allow local file:// access
        exchange.sendResponseHeaders(200, bytes.length);

        try (OutputStream os = exchange.getResponseBody()) {
            os.write(bytes);
        }
    }

    private void handleHealth(HttpExchange exchange) throws IOException {
        byte[] bytes = "{\"status\":\"ok\"}".getBytes(StandardCharsets.UTF_8);
        exchange.getResponseHeaders().add("Content-Type", "application/json");
        exchange.sendResponseHeaders(200, bytes.length);
        try (OutputStream os = exchange.getResponseBody()) {
            os.write(bytes);
        }
    }

    // ------------------------------------------------------------------ //
    //  JSON builder  (hand-rolled to avoid adding a dependency)
    // ------------------------------------------------------------------ //

    private String buildJson() {
        List<VisualMessage> messages = contentManager.getAllMessages();
        StringBuilder sb = new StringBuilder("[");

        for (int i = 0; i < messages.size(); i++) {
            VisualMessage m = messages.get(i);

            // relation: stored in variables map; default 0 (root)
            int relation = 0;
            if (m.variables != null && m.variables.containsKey("relation")) {
                try {
                    relation = Integer.parseInt(m.variables.get("relation").toString());
                } catch (NumberFormatException ignored) {}
            }

            sb.append("{");
            sb.append("\"id\":").append(m.id).append(",");
            sb.append("\"author\":").append(jsonString(m.author)).append(",");
            sb.append("\"content\":").append(jsonString(m.content)).append(",");
            sb.append("\"original\":").append(m.original).append(",");
            sb.append("\"timestamp\":").append(m.timestamp).append(",");
            sb.append("\"relation\":").append(relation).append(",");

            // OPTIONAL: expose topics if useful in UI
            sb.append("\"topics\":[");
            for (int t = 0; t < m.topics.size(); t++) {
                sb.append(jsonString(m.topics.get(t)));
                if (t < m.topics.size() - 1) sb.append(",");
            }
            sb.append("],");

            sb.append("\"reactions\":[");

            if (m.reactions != null) {
                for (int j = 0; j < m.reactions.size(); j++) {
                    var r = m.reactions.get(j);
                    sb.append("{");
                    sb.append("\"author\":").append(jsonString(r.author())).append(",");
                    sb.append("\"reaction\":").append(jsonString(r.reaction()));
                    sb.append("}");
                    if (j < m.reactions.size() - 1) sb.append(",");
                }
            }

            sb.append("]}");

            if (i < messages.size() - 1) sb.append(",");
        }

        sb.append("]");
        return sb.toString();
    }
    
    /** Minimal JSON string escaping. */
    private String jsonString(String s) {
        if (s == null) return "null";
        return "\"" + s
            .replace("\\", "\\\\")
            .replace("\"", "\\\"")
            .replace("\n", "\\n")
            .replace("\r", "\\r")
            .replace("\t", "\\t")
            + "\"";
    }
}
