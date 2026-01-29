package arch;

import jason.asSyntax.Term;

public interface LlmAgArch {
    String createContent(Term topics, Term variables);

    String createContent(Term interpretations, Term originalContent, Term topics, Term variables);

    String sentiment(Term text);

    int updateLove(
        Term group, 
        Term current, 
        Term political_standpoint, 
        Term demographics,
        Term persona_description, 
        Term content);

    int updateHate(
        Term group, 
        Term current, 
        Term political_standpoint, 
        Term demographics,
        Term persona_description, 
        Term content);
}
