package arch;

import jason.asSyntax.Term;

public interface LlmAgArch {
    String createContent(Term topics, Term variables);

    String createContent(Term interpretations, Term originalContent, Term topics, Term variables);

    String sentiment(String text);

    int updateLove(
        String group, 
        String current, 
        String political_standpoint, 
        String demographics,
        String persona_description, 
        String content);

    int updateHate(
        String group, 
        String current, 
        String political_standpoint, 
        String demographics,
        String persona_description, 
        String content);
}
