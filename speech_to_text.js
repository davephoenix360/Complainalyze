const speech = require("@google-cloud/speech");
const fs = require("fs");
const dotenv = require("dotenv");
dotenv.config();

async function main() {
  const client = new speech.SpeechClient();
  const fileName = "./s-to-t_test.m4a";

  const file = fs.readFileSync(fileName);
  const audioBytes = file.toString("base64");

  const audio = {
    content: audioBytes,
  };

  const config = {
    encoding: "LINEAR16",
    sampleRateHertz: 16000,
    languageCode: "en-US",
  };
  const request = {
    audio: audio,
    config: config,
  };

  const [response] = await client.recognize(request);
  const transcription = response.results
    .map((result) => result.alternatives[0].transcript)
    .join("\n");
  console.log(`Transcript: ${transcription}`);
}

main().catch(console.error);
