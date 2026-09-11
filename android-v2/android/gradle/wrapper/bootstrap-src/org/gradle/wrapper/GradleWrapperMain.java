package org.gradle.wrapper;

import java.io.IOException;
import java.io.InputStream;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.time.Duration;
import java.util.Comparator;
import java.util.Properties;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

/**
 * Small self-contained Gradle bootstrap used because this handoff environment cannot
 * fetch the official gradle-wrapper.jar binary. It reads gradle-wrapper.properties,
 * downloads the configured Gradle distribution into GRADLE_USER_HOME, then delegates
 * all arguments to that Gradle executable. Requires Java 17+.
 */
public final class GradleWrapperMain {
    private GradleWrapperMain() {}

    public static void main(String[] args) throws Exception {
        Path appHome = locateAppHome();
        Properties props = loadProperties(appHome);
        String distributionUrl = required(props, "distributionUrl");
        int timeoutMillis = Integer.parseInt(props.getProperty("networkTimeout", "10000"));

        Path userHome = gradleUserHome();
        String version = parseVersion(distributionUrl);
        Path installRoot = userHome.resolve("wrapper").resolve("dists").resolve("jinju-bus").resolve("gradle-" + version);
        Path gradleHome = installRoot.resolve("gradle-" + version);

        if (!Files.isRegularFile(gradleExecutable(gradleHome))) {
            installDistribution(distributionUrl, installRoot, gradleHome, timeoutMillis);
        }

        int exit = launchGradle(gradleHome, args);
        System.exit(exit);
    }

    private static Path locateAppHome() throws Exception {
        URI jar = GradleWrapperMain.class.getProtectionDomain().getCodeSource().getLocation().toURI();
        Path wrapperJar = Path.of(jar).toAbsolutePath().normalize();
        Path wrapperDir = Files.isDirectory(wrapperJar) ? wrapperJar : wrapperJar.getParent();
        if (wrapperDir == null || wrapperDir.getParent() == null || wrapperDir.getParent().getParent() == null) {
            throw new IllegalStateException("Cannot determine Gradle wrapper project directory");
        }
        return wrapperDir.getParent().getParent();
    }

    private static Properties loadProperties(Path appHome) throws IOException {
        Path file = appHome.resolve("gradle").resolve("wrapper").resolve("gradle-wrapper.properties");
        Properties props = new Properties();
        try (InputStream input = Files.newInputStream(file)) {
            props.load(input);
        }
        return props;
    }

    private static String required(Properties props, String key) {
        String value = props.getProperty(key);
        if (value == null || value.isBlank()) throw new IllegalStateException("Missing " + key);
        return value;
    }

    private static Path gradleUserHome() {
        String configured = System.getenv("GRADLE_USER_HOME");
        if (configured != null && !configured.isBlank()) return Path.of(configured);
        return Path.of(System.getProperty("user.home"), ".gradle");
    }

    private static String parseVersion(String url) {
        String name = url.substring(url.lastIndexOf('/') + 1);
        if (!name.startsWith("gradle-") || !name.endsWith("-bin.zip")) {
            throw new IllegalArgumentException("Unsupported Gradle distribution URL: " + url);
        }
        return name.substring("gradle-".length(), name.length() - "-bin.zip".length());
    }

    private static Path gradleExecutable(Path gradleHome) {
        boolean windows = System.getProperty("os.name", "").toLowerCase().contains("win");
        return gradleHome.resolve("bin").resolve(windows ? "gradle.bat" : "gradle");
    }

    private static void installDistribution(String url, Path installRoot, Path gradleHome, int timeoutMillis) throws Exception {
        Files.createDirectories(installRoot);
        Path zip = installRoot.resolve("distribution.zip");
        Path partial = installRoot.resolve("distribution.zip.part");

        System.err.println("Downloading " + url);
        HttpClient client = HttpClient.newBuilder()
            .followRedirects(HttpClient.Redirect.NORMAL)
            .connectTimeout(Duration.ofMillis(timeoutMillis))
            .build();
        HttpRequest request = HttpRequest.newBuilder(URI.create(url))
            .timeout(Duration.ofMinutes(10))
            .GET()
            .build();
        HttpResponse<Path> response = client.send(request, HttpResponse.BodyHandlers.ofFile(partial));
        if (response.statusCode() < 200 || response.statusCode() >= 300) {
            Files.deleteIfExists(partial);
            throw new IOException("Gradle distribution download failed: HTTP " + response.statusCode());
        }
        Files.move(partial, zip, StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);

        Path tempDir = installRoot.resolve("unpack.tmp");
        deleteRecursively(tempDir);
        Files.createDirectories(tempDir);
        unzip(zip, tempDir);
        Path unpacked = tempDir.resolve(gradleHome.getFileName());
        if (!Files.isDirectory(unpacked)) {
            deleteRecursively(tempDir);
            throw new IOException("Unexpected Gradle ZIP layout: " + unpacked + " missing");
        }
        deleteRecursively(gradleHome);
        Files.move(unpacked, gradleHome, StandardCopyOption.REPLACE_EXISTING);
        deleteRecursively(tempDir);
        Files.deleteIfExists(zip);

        Path executable = gradleExecutable(gradleHome);
        if (!System.getProperty("os.name", "").toLowerCase().contains("win")) {
            executable.toFile().setExecutable(true, false);
        }
    }

    private static void unzip(Path zip, Path destination) throws IOException {
        try (ZipInputStream input = new ZipInputStream(Files.newInputStream(zip))) {
            ZipEntry entry;
            while ((entry = input.getNextEntry()) != null) {
                Path output = destination.resolve(entry.getName()).normalize();
                if (!output.startsWith(destination)) throw new IOException("Blocked unsafe ZIP entry: " + entry.getName());
                if (entry.isDirectory()) {
                    Files.createDirectories(output);
                } else {
                    Files.createDirectories(output.getParent());
                    Files.copy(input, output, StandardCopyOption.REPLACE_EXISTING);
                }
                input.closeEntry();
            }
        }
    }

    static String[] buildLaunchCommand(Path executable, String[] args, boolean windows, String comSpec) {
        if (windows) {
            String shell = (comSpec == null || comSpec.isBlank()) ? "cmd.exe" : comSpec;
            String[] command = new String[args.length + 4];
            command[0] = shell;
            command[1] = "/d";
            command[2] = "/c";
            command[3] = executable.toString();
            System.arraycopy(args, 0, command, 4, args.length);
            return command;
        }
        String[] command = new String[args.length + 1];
        command[0] = executable.toString();
        System.arraycopy(args, 0, command, 1, args.length);
        return command;
    }

    private static int launchGradle(Path gradleHome, String[] args) throws IOException, InterruptedException {
        boolean windows = System.getProperty("os.name", "").toLowerCase().contains("win");
        Path executable = gradleExecutable(gradleHome);
        String[] command = buildLaunchCommand(executable, args, windows, System.getenv("ComSpec"));
        Process process = new ProcessBuilder(command)
            .directory(Path.of(System.getProperty("user.dir")).toFile())
            .inheritIO()
            .start();
        return process.waitFor();
    }

    private static void deleteRecursively(Path path) throws IOException {
        if (!Files.exists(path)) return;
        try (var stream = Files.walk(path)) {
            for (Path current : stream.sorted(Comparator.reverseOrder()).toList()) {
                Files.deleteIfExists(current);
            }
        }
    }
}
