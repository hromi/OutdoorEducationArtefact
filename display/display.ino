/*
Core of the solar display client 
Daniel Hromada & Nik Kapanadze for teacher.solar project
 UdK / ECDF AE520307 conditions of morally restricted GPL licence (mrGPL) apply
 */

#include <SPI.h>
#include <WiFiNINA.h>
#include "epd5in65f.h"

#define SIZE 134400
#define OFFSET 448

unsigned char m_image[SIZE+OFFSET];

//#include "arduino_secrets.h"
///////please enter your sensitive data in the Secret tab/arduino_secrets.h

char ssid[20] = "FibelNet";       
char pass[20] = "cirrostratus";     
char server[20] = "gardens.digital";    // name address for Google (using DNS)
char file[20] = "/folio.dat";

int status = WL_IDLE_STATUS;
WiFiSSLClient client;
Epd epd;

void setup() {

  Serial.begin(9600);
  //while (!Serial) {
  //  ; // wait for serial port to connect. Needed for native USB port only
  //}
   if (Serial) {Serial.println("RESET");}
    epd.Reset();

  int rc = epd.Init();
  

  if (rc != 0) {
    if (Serial) {Serial.println("e-Paper init failed with code");}
    return;
  }
  else{
    if (Serial) {Serial.println("e-Paper initialized");}
  }

  epd.Clear(0);

  if (WiFi.status() == WL_NO_MODULE) {
    if (Serial) {Serial.println("Communication with WiFi module failed!");}
    // don't continue
    while (true);
  }

  // attempt to connect to Wifi network:
  while (status != WL_CONNECTED) {
    if (Serial) {Serial.print("Attempting to connect to SSID: ");}
    if (Serial) {Serial.println(ssid);}
    status = WiFi.begin(ssid, pass);
    // waait some time for connection:
    delay(3000);
  }
  if (Serial) {Serial.println("Connected to wifi");}
  printWifiStatus();
}


void loop() {

int idx=OFFSET;

  if (client.connectSSL(server, 443)) {
    if (Serial) {Serial.println("connected to server");}
    client.print("GET ");
    client.print(file);
    client.println(" HTTP/1.1");
    client.print("GET ");
    client.print(file);
    client.println(" HTTP/1.1");
    client.print("Host: ");
    client.println(server);
    client.println("Connection: close");
    client.println();
    //epd.Clear(0);
    if (Serial) {Serial.println("receiving response");}

  //delay is necessary so that the response can arrive
  //delay(100);
  while (idx<SIZE+OFFSET) {
    //note:one could potentially feed the display directly from this loop, thus saving memory for more useful stuff
    if (client.available()){ 
      char c = client.read();
      //Serial.write(c);
      if (idx<0) {
        m_image[SIZE-idx]=c;
      } else {
        m_image[idx]=c;
      }
      idx++;
    }
  }
  //client.read(m_image,SIZE);
  //Serial.print(idx);
  if (Serial) {Serial.println("idx :: displaying folio");}
  epd.EPD_5IN65F_Display(m_image);
    if (Serial) {Serial.println("foliodisplayed ");}

  }
  delay(3000);
}


void printWifiStatus() {
  if (Serial) {Serial.print("SSID: ");}
  if (Serial) {Serial.println(WiFi.SSID());}
  IPAddress ip = WiFi.localIP();
  if (Serial) {Serial.print("IP Address: ");}
  if (Serial) {Serial.println(ip);}
  long rssi = WiFi.RSSI();
  if (Serial) {Serial.print("signal strength (RSSI):");}
  if (Serial) {Serial.print(rssi);}
  if (Serial) {Serial.println(" dBm");}
}