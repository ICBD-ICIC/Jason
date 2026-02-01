package arch;

import jason.asSyntax.Term;

public interface LlmAgArch {
    String createContent(Term topics, Term variables);

    String createContent(Term interpretations, Term originalContent, Term topics, Term variables);

    String reply(Term politicalStandpoint, Term demographics, Term personaDescription, Term conversation);

    String sentiment(Term text);

    int updateLove(
        Term group, 
        Term current, 
        Term politicalStandpoint, 
        Term demographics,
        Term personaDescription, 
        Term content);

    int updateHate(
        Term group, 
        Term current, 
        Term politicalStandpoint, 
        Term demographics,
        Term personaDescription, 
        Term content);
    
    int initiateLove(
        Term group, 
        Term politicalStandpoint, 
        Term demographics,
        Term personaDescription);

    int initiateHate(
        Term group,
        Term politicalStandpoint, 
        Term demographics,
        Term personaDescription);
}
