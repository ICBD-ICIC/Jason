package arch;

import jason.asSyntax.Term;
import java.util.Map;

public interface SocialAgArch {
    String createContent(Term topics, Term variables);

    Map<String, Object> interpretContent(Term content);
}
