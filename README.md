# MarktplaatsScanner
Scanner app om de barcodes gelinkt aan de productmanager te scannen met een USB scanner om productinformatie en verkoopstatus op te halen. Wordt nog uitgebreid met kopersinformatie en smartphone app zodat producten die bij de kassa worden opgehaald geverifieerd kunnen worden in ontvanger en verkoopprijs.

https://github.com/user-attachments/assets/d5e1661d-ea55-4c6c-b441-825336e96cda

# MPScanner Android

https://github.com/user-attachments/assets/4e877826-f4dc-4266-af9e-980363b80a28

Huidige APK: https://kdrive.infomaniak.com/app/share/2309692/a594e0ab-7348-4fe6-a76e-2342ffee404f

Installatie:
1. Laat Android Studio synchroniseren
Zodra het project open is, start Android Studio automatisch een Gradle-sync (of klik rechtsboven op het olifantje/🐘-icoon "Sync Project with Gradle Files" als het niet vanzelf gebeurt). Dit kan een paar minuten duren — hij downloadt de juiste Gradle-versie en Android SDK-onderdelen.

2. Los eventuele meldingen op die daarbij verschijnen

Vraagt hij om de Android SDK Platform 34 te installeren? → accepteren.
Klaagt hij dat de Gradle-wrapper (gradlew/wrapper-jar) ontbreekt? Dat kan, want ik heb alleen gradle-wrapper.properties meegeleverd, niet de binaire jar zelf. Android Studio biedt dit meestal vanzelf aan om te herstellen — accepteer dat. Lukt dat niet automatisch, ga naar Android Studio → Settings → Build, Execution, Deployment → Gradle, zet "Gradle JDK"/"Use Gradle from" tijdelijk op een lokale installatie, sync opnieuw, en Android Studio vult de ontbrekende wrapper-bestanden dan zelf aan.

3. Sluit een telefoon aan (aanbevolen) of gebruik een emulator

Telefoon (beter, want camera nodig): zet op je Android-telefoon Instellingen → Over telefoon → tik 7x op buildnummer (activeert ontwikkelaarsopties), dan Instellingen → Ontwikkelaarsopties → USB-debugging aan. Sluit 'm aan met USB, accepteer de "toestaan"-popup op je telefoon.
Emulator: kan ook, maar barcodescannen via de webcam van je pc werkt in een emulator vaak onbetrouwbaar/niet — voor het echte testen is een telefoon simpeler.

4. Klik op de groene ▶️ Run-knop (bovenin), kies je toestel, en de app wordt gebouwd + geïnstalleerd.

5. Eerste keer opstarten op de telefoon: Geef camera-toestemming als daarom gevraagd wordt.

6. Tik op "📁 Kies Syncthing-map" en selecteer de map die Syncthing naar je telefoon synct (die moet producten.xml bevatten — check dus even dat het XML-pad in Productmanager's instellingen binnen die gesyncte map valt). Richt de camera op een barcode die Productmanager gegenereerd heeft → de gegevens zouden moeten verschijnen.

7. Snelste manier: debug-APK. In Android Studio, bovenin het menu: Build → Build Bundle(s) / APK(s) → Build APK(s). Wacht tot de build klaar is — rechtsonder verschijnt een meldingsballonnetje "APK(s) generated successfully" met een link "locate". Dat bestand is je installeerbare APK.

8. Kopieer app-debug.apk naar je telefoon — makkelijkste opties:

USB: sluit de telefoon aan, sleep het bestand naar de telefoon-opslag via je bestandsbeheerder op de pc.
Cloud/mail: stuur 'm naar jezelf (Google Drive, e-mail, etc.) en download 'm op de telefoon.
ADB (als je toch al verbonden bent):
bash  adb install android/app/build/outputs/apk/debug/app-debug.apk

