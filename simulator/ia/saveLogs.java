package ia;

import jason.asSemantics.*;
import jason.asSyntax.*;

import java.io.BufferedWriter;
import java.io.File;
import java.io.FileWriter;
import java.io.IOException;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

import com.fasterxml.jackson.databind.ObjectMapper;

import lib.JasonToJavaTranslator;

public class saveLogs extends DefaultInternalAction {

    private static final String LOGS_FOLDER = "logs/" + System.currentTimeMillis() + "/";
    private static final ObjectMapper mapper = new ObjectMapper();

    // One single-threaded executor per agent file — guarantees order, non-blocking for caller
    private static final ConcurrentHashMap<String, ExecutorService> executors = new ConcurrentHashMap<>();
    private static final ConcurrentHashMap<String, BufferedWriter> writers = new ConcurrentHashMap<>();

    static {
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            // Stop accepting new tasks
            for (ExecutorService ex : executors.values()) {
                ex.shutdown();
            }
            // Wait for pending writes to finish
            for (ExecutorService ex : executors.values()) {
                try { ex.awaitTermination(10, TimeUnit.SECONDS); } 
                catch (InterruptedException ignored) {}
            }
            // Final flush and close
            for (BufferedWriter w : writers.values()) {
                try { w.flush(); w.close(); } 
                catch (IOException ignored) {}
            }
        }));
    }

    @Override
    public Object execute(TransitionSystem ts, Unifier un, Term[] args) throws Exception {
        if (args.length != 1) {
            throw new IllegalArgumentException("saveLogs expects 1 argument");
        }

        String agentName = ts.getAgArch().getAgName();
        Map<String, Object> data = JasonToJavaTranslator.translateVariables(args[0]);
        data.put("timestamp", System.currentTimeMillis());
        String json = mapper.writeValueAsString(data);

        // Get or create a single-threaded executor for this agent
        ExecutorService executor = executors.computeIfAbsent(agentName, name ->
            Executors.newSingleThreadExecutor(r -> {
                Thread t = new Thread(r, "log-writer-" + name);
                t.setDaemon(false); // non-daemon so shutdown hook can drain it
                return t;
            })
        );

        executor.submit(() -> {
            try {
                BufferedWriter writer = writers.computeIfAbsent(agentName, name -> {
                    try {
                        File dir = new File(LOGS_FOLDER);
                        if (!dir.exists()) dir.mkdirs();
                        return new BufferedWriter(new FileWriter(LOGS_FOLDER + name + ".jsonl", true));
                    } catch (IOException e) {
                        throw new RuntimeException(e);
                    }
                });
                writer.write(json);
                writer.newLine();
                writer.flush();
            } catch (IOException e) {
                System.err.println("[saveLogs] Write failed for " + agentName + ": " + e.getMessage());
            }
        });

        return true;
    }
}