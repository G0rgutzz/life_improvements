import datetime
import os.path
import pickle
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import pandas as pd

# Zakres API
SCOPES = ['https://www.googleapis.com/auth/calendar.events.readonly']


# Funkcja do autoryzacji
def get_credentials():
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('file_path', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    return creds


# Główna funkcja
def main():
    creds = get_credentials()
    try:
        service = build('calendar', 'v3', credentials=creds)
        print("Połączenie z Google Calendar API udane!")

        # Pobierz mapę kolorów (opcjonalnie)
        colors = service.colors().get().execute()
        print("Kolory załadowane.")

        # Ustaw zakres czasu
        now = datetime.datetime.utcnow().isoformat() + 'Z'
        month_ago = (datetime.datetime.utcnow() - datetime.timedelta(days=35)).isoformat() + 'Z'

        # Pobierz wydarzenia (z paginacją – WSZYSTKIE!)
        print("Pobieranie wydarzeń (z paginacją)...")
        events = []
        page_token = None

        while True:
            events_list = service.events().list(
                calendarId='primary',
                timeMin=month_ago,
                timeMax=now,
                singleEvents=True,
                orderBy='startTime',
                maxResults=250,
                pageToken=page_token
            )
            batch = events_list.execute()
            events.extend(batch.get('items', []))
            page_token = batch.get('nextPageToken')
            if not page_token:
                break
            print(f"   → Pobrano kolejną stronę ({len(batch.get('items', []))} wydarzeń)...")

        print(f"Łącznie pobrano {len(events)} wydarzeń z kalendarza.")

        if not events:
            print('Brak wydarzeń.')
            return

        # Przetwórz dane (jak wcześniej)
        data = []
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            color_id = event.get('colorId', 'Brak')
            status = event.get('status', 'confirmed')

            if status == 'cancelled':
                event_status = 'Odwołane'
            elif color_id == '11':
                event_status = 'Odwołane wcześniej'
            elif color_id == '6':
                event_status = 'Odwołane za późno'
            elif color_id in ['1', '2', '7', '9', '10']:
                event_status = 'Odbyło się normalnie'
            else:
                event_status = 'Nieznany'

            data.append({
                'Tytuł': event.get('summary', 'Brak tytułu'),
                'Data startu': start,
                'Color ID': color_id,
                'Status API': status,
                'Oznaczony status': event_status
            })

        # === PRZETWARZANIE I ZAPIS ===
        df = pd.DataFrame(data)

        # 1. Zliczanie identycznych wydarzeń
        df = zlicz_wydarzenia(df)

        # 2. Obliczanie frekwencji
        df, frekwencja_podsumowanie = oblicz_frekwencje(df)

        # 3. Zapisz do Excela (dwa arkusze!)
        with pd.ExcelWriter('kalendarz_dane.xlsx', engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Szczegóły', index=False)
            frekwencja_podsumowanie.to_excel(writer, sheet_name='Podsumowanie frekwencji', index=False)

        # 4. Wypisz podsumowanie w konsoli
        print("\n" + "=" * 50)
        print("PODSUMOWANIE FREKWENCJI")
        print("=" * 50)
        for _, row in frekwencja_podsumowanie.iterrows():
            print(f"{row['Status frekwencji']:25}: {row['Liczba']:3} ({row['Procent']})")
        print("=" * 50)

    except Exception as e:
        print(f"\nBŁĄD API: {e}")
        print("Sprawdź:")
        print("  1. Czy SCOPES = ['https://www.googleapis.com/auth/calendar.events.readonly']")
        print("  2. Czy usunąłeś token.pickle")
        print("  3. Czy dodałeś swój e-mail do Test Users w OAuth consent screen")
        return


def zlicz_wydarzenia(df):
    """
    Zlicza, ile razy to samo wydarzenie się powtarza (ten sam tytuł + data + godzina).
    Dodaje kolumnę 'Liczba powtórzeń'.
    """
    # Tworzymy klucz: Tytuł
    df['Klucz'] = df['Tytuł'].astype(str)

    # Zliczamy powtórzenia
    powtorzenia = df['Klucz'].value_counts().reset_index()
    powtorzenia.columns = ['Klucz', 'Liczba powtórzeń']

    # Łączymy z oryginalnym df
    df = df.merge(powtorzenia, on='Klucz', how='left')

    # Usuwamy pomocniczy klucz
    df = df.drop(columns=['Klucz'])

    return df


def oblicz_frekwencje(df):
    """
    Liczy frekwencję na podstawie kolorów:
    - Zielony/Niebieski/Lawendowy → Obecny
    - Czerwony → Odwołane wcześniej
    - Pomarańczowy → Odwołane za późno
    Zwraca podsumowanie w formie DataFrame.
    """
    # Mapowanie kolorów na status frekwencji
    frekwencja_map = {
        '11': 'Odwołane wcześniej',  # Czerwony
        '6': 'Odwołane za późno',  # Pomarańczowy
    }
    obecny_kolory = ['1', '2', '7', '9', '10','Brak']  # Lawendowy, zielony, niebieski, domyślny - Brak

    # Tworzymy kolumnę "Frekwencja"
    df['Frekwencja'] = df['Color ID'].apply(
        lambda x: frekwencja_map.get(x,
                                     'Obecny' if x in obecny_kolory else 'Nieznany'
                                     )
    )

    # Podsumowanie frekwencji
    podsumowanie = df['Frekwencja'].value_counts().reset_index()
    podsumowanie.columns = ['Status frekwencji', 'Liczba']

    # Dodajemy procenty
    total = podsumowanie['Liczba'].sum()
    podsumowanie['Procent'] = (podsumowanie['Liczba'] / total * 100).round(2)
    podsumowanie['Procent'] = podsumowanie['Procent'].astype(str) + '%'

    return df, podsumowanie


if __name__ == '__main__':
    main()