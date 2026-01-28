package arch;

import jason.asSyntax.Term;

public interface LlmAgArch {
    String createContent(Term topics, Term variables);

    String createContent(Term interpretations, Term originalContent, Term topics, Term variables);

    String sentiment(String text);
}
