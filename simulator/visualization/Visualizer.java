package visualization;

/**
 * Modular visualizer interface.
 * Implement this to create experiment-specific visualizations.
 * Swap implementations via Env constructor or config.
 */
public interface Visualizer {

    /**
     * Called once when the environment initializes.
     * Use to start servers, open windows, etc.
     */
    void start();

    /**
     * Called whenever the message state changes
     * (new post, repost, comment, reaction).
     * The visualizer should pull fresh data from the ContentManager
     * or use the snapshot provided.
     */
    void onUpdate();

    /**
     * Called when the simulation ends.
     * Use to flush data, close connections, etc.
     */
    void stop();
}
