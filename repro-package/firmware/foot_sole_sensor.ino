#include <SPI.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>

#define MCP_CS   5
#define MCP_CLK  18
#define MCP_MISO 19
#define MCP_MOSI 23

int rowPins[8] = {13, 12, 14, 27, 26, 25, 33, 32};

int values[8][8];
int baseline[8][8];

const int DEAD_COLUMN = 3;

SPISettings mcpSettings(1000000, MSBFIRST, SPI_MODE0);

// ---- BLE setup ----
#define SERVICE_UUID        "12345678-1234-1234-1234-123456789abc"
#define CHARACTERISTIC_UUID "abcd1234-abcd-1234-abcd-1234567890ab"

BLECharacteristic *pCharacteristic;
bool deviceConnected = false;

class ServerCallbacks: public BLEServerCallbacks {
  void onConnect(BLEServer* pServer) { deviceConnected = true; }
  void onDisconnect(BLEServer* pServer) {
    deviceConnected = false;
    pServer->getAdvertising()->start();  // restart advertising after disconnect
  }
};

int readMCP3008(int channel) {
  if (channel < 0 || channel > 7) return 0;
  SPI.beginTransaction(mcpSettings);
  digitalWrite(MCP_CS, LOW);
  SPI.transfer(0x01);
  int highByte = SPI.transfer(0x80 | (channel << 4));
  int lowByte  = SPI.transfer(0x00);
  digitalWrite(MCP_CS, HIGH);
  SPI.endTransaction();
  return ((highByte & 0x03) << 8) | lowByte;
}

int readMCP3008Avg(int channel, int samples = 4) {
  long sum = 0;
  for (int i = 0; i < samples; i++) sum += readMCP3008(channel);
  return sum / samples;
}

void scanMatrix(int (&target)[8][8]) {
  for (int r = 0; r < 8; r++) {
    for (int i = 0; i < 8; i++) digitalWrite(rowPins[i], LOW);
    digitalWrite(rowPins[r], HIGH);
    delayMicroseconds(1000);
    for (int c = 0; c < 8; c++) target[r][c] = readMCP3008Avg(c, 4);
    digitalWrite(rowPins[r], LOW);
  }
}

void calibrateBaseline() {
  long sum[8][8] = {0};
  int calibSamples = 10;
  for (int s = 0; s < calibSamples; s++) {
    scanMatrix(values);
    for (int r = 0; r < 8; r++)
      for (int c = 0; c < 8; c++)
        sum[r][c] += values[r][c];
    delay(50);
  }
  for (int r = 0; r < 8; r++)
    for (int c = 0; c < 8; c++)
      baseline[r][c] = sum[r][c] / calibSamples;
}


void sendRow(int r) {
  uint8_t packet[17];
  packet[0] = (uint8_t)r;
  for (int c = 0; c < 8; c++) {
    int16_t delta = (int16_t)(values[r][c] - baseline[r][c]);
    if (c == DEAD_COLUMN) delta = 0;  // unreliable channel, mask at the source
    packet[1 + c * 2]     = (uint8_t)(delta & 0xFF);
    packet[1 + c * 2 + 1] = (uint8_t)((delta >> 8) & 0xFF);
  }
  pCharacteristic->setValue(packet, sizeof(packet));
  pCharacteristic->notify();
}


void printSerialPlotter() {
  for (int r = 0; r < 8; r++) {
    int rowMax = 0;
    for (int c = 0; c < 8; c++) {
      if (c == DEAD_COLUMN) continue;
      int delta = values[r][c] - baseline[r][c];
      if (delta > rowMax) rowMax = delta;
    }
    Serial.print("R");
    Serial.print(r);
    Serial.print(":");
    Serial.print(rowMax);
    Serial.print(r == 7 ? "\n" : "\t");
  }
}

void setup() {
  Serial.begin(115200);
  delay(1000);

  SPI.begin(MCP_CLK, MCP_MISO, MCP_MOSI, MCP_CS);
  pinMode(MCP_CS, OUTPUT);
  digitalWrite(MCP_CS, HIGH);

  for (int r = 0; r < 8; r++) {
    pinMode(rowPins[r], OUTPUT);
    digitalWrite(rowPins[r], LOW);
  }

  Serial.println("Calibrating baseline, keep sensor untouched...");
  calibrateBaseline();
  Serial.println("Calibration done.");


  Serial.println("Baseline matrix (row: col0 col1 ... col7):");
  for (int r = 0; r < 8; r++) {
    for (int c = 0; c < 8; c++) {
      Serial.print(baseline[r][c]);
      Serial.print(c == 7 ? "\n" : "\t");
    }
  }

  // ---- BLE init ----
  BLEDevice::init("ESP32_FootSensor");
  BLEDevice::setMTU(247);  // ask for a larger MTU where supported; not required


  BLEServer *pServer = BLEDevice::createServer();
  pServer->setCallbacks(new ServerCallbacks());

  BLEService *pService = pServer->createService(SERVICE_UUID);
  pCharacteristic = pService->createCharacteristic(
    CHARACTERISTIC_UUID,
    BLECharacteristic::PROPERTY_READ | BLECharacteristic::PROPERTY_NOTIFY
  );
  pCharacteristic->addDescriptor(new BLE2902());
  pService->start();

  BLEAdvertising *pAdvertising = BLEDevice::getAdvertising();
  pAdvertising->addServiceUUID(SERVICE_UUID);
  pAdvertising->start();

  Serial.println("BLE advertising started, waiting for connection...");
}

void loop() {
  scanMatrix(values);

  printSerialPlotter();

  if (deviceConnected) {
    for (int r = 0; r < 8; r++) {
      sendRow(r);
      delay(10);  // small gap so the BLE stack's notify queue isn't flooded
    }
  }

  delay(20);  // total frame period ~= 8*10 + 20 = 100ms -> ~10 fps
}