package arch.schema;

import com.google.genai.types.Schema;
import com.google.genai.types.Type;

import java.util.List;
import java.util.Map;

public class GeminiSchemas {

    public static final Schema DECISION_SCHEMA =
        Schema.builder()
            .type(Type.Known.OBJECT)
            .properties(Map.of(

                "new_state",
                Schema.builder()
                    .type(Type.Known.STRING)
                    .build(),

                "reply_content",
                Schema.builder()
                    .type(Type.Known.STRING)
                    .build(),

                "topics",
                Schema.builder()
                    .type(Type.Known.ARRAY)
                    .items(
                        Schema.builder()
                            .type(Type.Known.STRING)
                            .build()
                    )
                    .build()

            ))
            .required(List.of(
                "new_state",
                "reply_content",
                "topics"
            ))
            .build();

    private GeminiSchemas() {
        // utility class
    }
}