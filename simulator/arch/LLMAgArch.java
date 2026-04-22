package arch;

import jason.architecture.AgArch;
import jason.asSyntax.Term;

import java.util.Map;

/**
 * Abstract base for LLM-backed agent architectures.
 *
 * Handles retry logic and the Gemini client lifecycle so that
 * subclasses only need to implement prompt construction and
 * response parsing. Swapping to a different LLM provider only
 * requires a new subclass — the BDI cycle and retry mechanism
 * stay here.
 */
public abstract class LLMAgArch extends AgArch implements SocialAgArch {

    protected static final int    MAX_RETRIES  = 3;
    protected static final long   RETRY_DELAY  = 1000L;

    /**
     * Sends a prompt to the LLM and returns the raw text response.
     * Retries up to MAX_RETRIES times on failure.
     */
    protected abstract String getResponse(String prompt);

    /**
     * Builds and sends the prompt for content creation.
     * Subclasses define how topics/variables map to a prompt.
     */
    @Override
    public abstract String createContent(Term topics, Term variables);

    /**
     * Builds and sends the prompt for content interpretation.
     * Subclasses define what the LLM is asked to extract.
     */
    @Override
    public abstract Map<String, Object> interpretContent(Term content);
}
