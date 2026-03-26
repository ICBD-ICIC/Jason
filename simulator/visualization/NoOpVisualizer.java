package visualization;

/**
 * Default no-op visualizer. Used when no visualization is needed.
 * Swap for KialoTreeVisualizer (or others) in Env to enable visualization.
 */
public class NoOpVisualizer implements Visualizer {
    @Override public void start() {}
    @Override public void onUpdate() {}
    @Override public void stop() {}
}
