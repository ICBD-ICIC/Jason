package ia;

import jason.asSemantics.*;
import jason.asSyntax.*;

import java.io.BufferedWriter;
import java.io.File;
import java.io.FileWriter;
import java.io.IOException;
import java.time.Instant;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

import com.fasterxml.jackson.databind.ObjectMapper;

import lib.JasonToJavaTranslator;

public class saveLogs extends DefaultInternalAction {

    private static final String LOGS_FOLDER = "logs/" + System.currentTimeMillis() + "/";
    private static final ConcurrentHashMap<String, BufferedWriter> writers = new ConcurrentHashMap<>();
    private static final ObjectMapper mapper = new ObjectMapper();

    @Override
    public Object execute(TransitionSystem ts, Unifier un, Term[] args) throws Exception {

        if (args.length != 1) {
            throw new IllegalArgumentException("saveLogs expects 1 argument: a list of variables");
        }

        Term listTerm = args[0];
        String agentName = ts.getAgArch().getAgName();
        Map<String, Object> data = JasonToJavaTranslator.translateVariables(listTerm);

        data.put("timestamp", System.currentTimeMillis());

        writeJsonToFile(agentName, data);
        return true;
    }

    private void writeJsonToFile(String agentName, Map<String, Object> data) throws IOException {
        String fileName = LOGS_FOLDER + agentName + ".jsonl";
        BufferedWriter writer = writers.computeIfAbsent(fileName, path -> {
            try {
                File dir = new File(LOGS_FOLDER);
                if (!dir.exists()) dir.mkdirs();
                return new BufferedWriter(new FileWriter(path, true));
            } catch (IOException e) {
                throw new RuntimeException("Failed to open log file: " + path, e);
            }
        });

        String json = mapper.writeValueAsString(data);

        // Synchronize per writer instance to prevent interleaved writes on the same file
        synchronized (writer) {
            writer.write(json);
            writer.newLine();
            writer.flush(); // flush after each write so logs aren't lost on crash
        }
    }
}