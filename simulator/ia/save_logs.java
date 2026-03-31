package ia;

import jason.asSemantics.*;
import jason.asSyntax.*;

import java.io.FileWriter;
import java.io.File;
import java.io.IOException;
import java.util.Map;

import com.fasterxml.jackson.databind.ObjectMapper;

import lib.JasonToJavaTranslator;

public class save_logs extends DefaultInternalAction {

    private static final String LOGS_FOLDER = "logs/";
    private static final ObjectMapper mapper = new ObjectMapper();

    @Override
    public Object execute(TransitionSystem ts, Unifier un, Term[] args) throws Exception {

        if (args.length != 1) {
            throw new IllegalArgumentException("save_logs expects 1 argument: a list of variables");
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

        File dir = new File(LOGS_FOLDER);
        if (!dir.exists()) {
            dir.mkdirs();
        }

        try (FileWriter file = new FileWriter(fileName, true)) {
            String json = mapper.writeValueAsString(data); 
            file.write(json + System.lineSeparator());
        }
    }
}