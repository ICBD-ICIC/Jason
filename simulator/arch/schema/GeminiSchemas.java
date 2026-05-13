package arch.schema;

import com.google.genai.types.Schema;
import com.google.genai.types.Type;

import java.util.List;

public class GeminiSchemas {

public static final Schema DECISION_SCHEMA =
    Schema.builder()
        .type(Type.Known.OBJECT)
        .properties(new java.util.LinkedHashMap<>() {{
            put("new_state",
                Schema.builder().type(Type.Known.STRING).build());
            put("reply_content",
                Schema.builder().type(Type.Known.STRING).build());
            put("topics",
                Schema.builder()
                    .type(Type.Known.ARRAY)
                    .items(Schema.builder().type(Type.Known.STRING).build())
                    .build());
        }})
        .required(List.of("new_state", "reply_content", "topics"))
        .build();

    private GeminiSchemas() {
        // utility class
    }
}