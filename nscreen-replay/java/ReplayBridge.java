import com.pulsepoint.hive.udf.calcscreen7ids.ResultEntry;
import com.pulsepoint.hive.udf.calcscreen7ids.calc.Screen7IdCalculatorDHMH;
import com.pulsepoint.hive.udf.louvain.Edge;
import com.pulsepoint.udf.ssus.udf.MurmurHash;
import java.io.*;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.util.*;

/** TSV bridge to unchanged Forge calculator and hash implementation. */
public class ReplayBridge {
    public static long hash(String value) {
        if (value.isEmpty()) return Long.MIN_VALUE;
        byte[] bytes = value.getBytes(StandardCharsets.UTF_8);
        long[] result = new long[2];
        MurmurHash.hash3_x64_128(ByteBuffer.wrap(bytes), 0, bytes.length, 0, result);
        return result[0] == Long.MIN_VALUE ? Long.MAX_VALUE : result[0];
    }

    private static String decode(String text) {
        return new String(Base64.getDecoder().decode(text), StandardCharsets.UTF_8);
    }

    public static void main(String[] args) throws Exception {
        if (args.length == 1 && args[0].equals("hash")) {
            try (BufferedReader reader = new BufferedReader(new InputStreamReader(System.in, StandardCharsets.UTF_8))) {
                for (String line; (line = reader.readLine()) != null;) System.out.println(hash(decode(line)));
            }
            return;
        }
        if (args.length != 2) throw new IllegalArgumentException("ReplayBridge input.tsv output.tsv");
        List<Edge> edges = new ArrayList<>();
        Map<String, Long> uids = new HashMap<>();
        try (BufferedReader reader = new BufferedReader(new FileReader(args[0], StandardCharsets.UTF_8))) {
            for (String line; (line = reader.readLine()) != null;) {
                String[] fields = line.split("\t", -1);
                if (fields.length != 5) throw new IllegalArgumentException("Expected five columns");
                String uid1 = decode(fields[0]);
                String uid2 = decode(fields[1]);
                long h1 = uids.computeIfAbsent(uid1, ReplayBridge::hash);
                long h2 = uids.computeIfAbsent(uid2, ReplayBridge::hash);
                edges.add(new Edge(h1, h2, Float.parseFloat(fields[2]),
                    Boolean.parseBoolean(fields[3]), Boolean.parseBoolean(fields[4])));
            }
        }
        Map<Long, ResultEntry> results = new HashMap<>();
        for (ResultEntry result : new Screen7IdCalculatorDHMH().calculateIds(edges)) results.put(result.uid, result);
        try (BufferedWriter writer = new BufferedWriter(new FileWriter(args[1], StandardCharsets.UTF_8))) {
            for (Map.Entry<String, Long> uid : uids.entrySet()) {
                ResultEntry result = results.get(uid.getValue());
                if (result == null) throw new IllegalStateException("Missing calculator result");
                writer.write(Base64.getEncoder().encodeToString(uid.getKey().getBytes(StandardCharsets.UTF_8)));
                writer.write("\t" + uid.getValue() + "\t" + result.deviceid + "\t" + result.matchid + "\t" + result.householdid + "\n");
            }
        }
        System.err.println("edges=" + edges.size() + " uids=" + uids.size() + " hashes=" + results.size());
    }
}
