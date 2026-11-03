# Teca Smart Routes próba – helyi változat

A Briochorama/Tesla Smart Routes 0.1.2 változatának felülvizsgált próbaágából készült. A csomag még nincs telepítve, és járművön nem lett tesztelve.

## Mit változtat a próbaág?

- A helyi aláíró HTTPS-kapcsolatát a tanúsítvány SHA-256 lenyomatával ellenőrzi. Nem kapcsolja ki az ellenőrzést `ssl=False` értékkel.
- A HTTP 200 önmagában nem siker: csak a tényleges logikai `result: true` válasz után jelez visszaigazolt küldést.
- A visszautasítás, a hibás válasz és az elérhetetlen jármű hibát jelez a Home Assistantnak.
- Egy útvonalból egyszerre egy küldés futhat. Nem ismétli automatikusan a navigációs parancsot.
- Az útvonalat és a helyazonosítókat a küldés előtt ellenőrzi.
- A helyadatok olvasására szolgáló `vehicle_location` OAuth-jogosultságot nem kéri. A bejelentkezés, a járműadatok és a járműparancsok szükséges jogai maradnak.
- Az aláíró a Tesla vehicle-command #443 módosításának rögzített `281b3a70caaef258e2f7dfe0136a2a192b8cb017` változatából épül.

## Eredeti források

- https://github.com/Briochorama/tesla-smart-routes — `b87a357cfd68d4aae63322be9de011adad5171d7`
- https://github.com/Briochorama/tesla-smart-routes-addon — `d8cc08e3a95e2ec3f089262fd4bd5b8d42455432`
- https://github.com/teslamotors/vehicle-command/pull/443

Az MIT licenc a LICENSE fájlban található. Az eredeti szerzők szerzői jogi közlései megmaradtak.

## Telepítési felépítés

A közzétételhez az `addons/teca_tesla_proxy` könyvtár a tárhely gyökerébe, `teca_tesla_proxy` néven kerül. A `custom_components/tesla_smart_routes` könyvtár HACS egyéni integrációként vagy kézi fájlmásolással telepíthető. A `.well-known/appspecific/com.tesla.3p.public-key.pem` csak a nyilvános járműkulcsot tartalmazza.

A privát járműkulcs külön, a Home Assistant `/config/tesla_smart_routes/private.pem` fájljába kerül. Nem része a nyilvános tárhelynek vagy a telepítőcsomagnak. Az aláíró a saját TLS-tanúsítványát a helyi adatkönyvtárában állítja elő, és csak a nyilvános SHA-256 lenyomatát írja ki a naplóba.

Az aláíró helyi 4443-as porton figyel. A küldéshez érvényes Tesla-hozzáférés és az autóban párosított kulcs kell. A TLS-lenyomat az első sikeres indulás naplójából másolható a Home Assistant integrációbeállításába.

## A még szükséges beállítások

1. Nyilvános GitHub Pages-tárhely létrehozása vagy az erre kijelölt meglévő tárhely használata.
2. A nyilvános kulcs közzététele és HTTPS-en történő ellenőrzése.
3. Tesla Developer alkalmazás létrehozása a nyilvános domainnel és a `https://my.home-assistant.io/redirect/oauth` visszatérési címmel.
4. Az európai Fleet API-partnerregisztráció elvégzése.
5. A helyi kulcs biztonságos átmásolása a Home Assistantra, majd az aláíró és az integráció telepítése.
6. A felhasználó Tesla-bejelentkezése, az új hozzáférés jóváhagyása és az autóban a kulcspárosítás.
7. A kiválasztott útvonal egyszeri próbája, majd az autó kijelzőjén a megállók ellenőrzése.

Az új Tesla-hozzáférés jóváhagyása, a szükséges jogi feltételek elfogadása és bármely fizetési beállítás a felhasználó döntése. A csomag nem tartalmaz automatikus fizetési műveletet vagy adatfolyam-konfigurálást.

## Ellenőrzés

A csomaghoz tartozó offline tesztek a megállók sorrendjét, a hibás/hiányzó adatokat, a HTTPS- és tanúsítványpin-követelményt, valamint az elutasító válaszok kezelését ellenőrzik. A Python-fájlok szintaktikai ellenőrzése sikeres. A Home Assistantba való betöltés, az OAuth-folyamat és az autós küldés még külön ellenőrzendő.
