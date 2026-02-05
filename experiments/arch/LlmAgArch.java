package arch;

import jason.asSyntax.Term;

public interface LlmAgArch {
    String createContent(Term topics, Term variables);

    String createContent(Term interpretations, Term originalContent, Term topics, Term variables);

    String reply(Term politicalStandpoint, Term demographics, Term personaDescription, Term conversation);

    String sentiment(Term text);

    Term affectivity(Term currentAffect, Term context, Term content);
}
