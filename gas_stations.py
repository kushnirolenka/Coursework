import streamlit as st
import mysql.connector
import folium
from streamlit_folium import folium_static
from geopy.geocoders import Nominatim
from geopy.distance import geodesic

FUEL_CONSUMPTION = {
    'бензин': 8.5,  # споживання бензину (л/100км)
    'дизель': 6.5     # споживання дизеля (л/100км)
}

# Функція для отримання даних про заправки з бази даних
def fetch_gas_stations_from_db():
    connection = mysql.connector.connect(
        host='localhost',
        user='root',
        password='root',
        database='map',
        auth_plugin='mysql_native_password'
    )

    cursor = connection.cursor()

    cursor.execute("SELECT id, name, latitude, longitude FROM gas_stations")
    gas_stations = cursor.fetchall()

    cursor.execute("SELECT name, rating FROM gas_stations_rating")
    gas_stations_rating = dict(cursor.fetchall())  # Зберігаємо рейтинги в словнику для зручного доступу

    cursor.close()
    connection.close()

    return gas_stations, gas_stations_rating

# Функція для обчислення відстані між двома точками
def calculate_distance(user_location, gas_station_location):
    return geodesic(user_location, gas_station_location).km

# Функція для обчислення палива, необхідного для подорожі певною відстанню
def calculate_fuel_needed(distance, fuel_consumption, motor_power):
    return (distance / 100) * fuel_consumption * motor_power

# Функція для генерації карти на основі місцезнаходження користувача
def generate_map(user_location, gas_stations, fuel_needed_gas_station):
    mymap = folium.Map(location=[user_location.latitude, user_location.longitude], zoom_start=14)
    
    # Додаємо маркер місцезнаходження користувача
    folium.Marker([user_location.latitude, user_location.longitude], popup="Ваше місцезнаходження", icon=folium.Icon(color='red')).add_to(mymap)
    
    # Додаємо маркери заправок з інформацією про необхідне паливо
    for station in gas_stations:
        for gas_station_info in fuel_needed_gas_station:
            if station[0] == gas_station_info[0]:
                popup_text = f"<b>Назва:</b> {station[1]}<br>"
                popup_text += f"<b>Рейтинг:</b> {gas_station_info[3]}<br>"
                popup_text += f"<b>Необхідне паливо:</b> {gas_station_info[4]:.2f} літрів<br>"
                 # Визначаємо колір маркера залежно від рейтингу
                rating = gas_station_info[3]
                if rating >= 8:
                    marker_color = 'green'
                elif rating >= 6:
                    marker_color = 'blue'
                else:
                    marker_color = 'orange'
                
                # Створюємо кастомну іконку з рейтингом
                icon_html = f"""
                <div style="
                    background-color: {marker_color};
                    color: white;
                    text-align: center;
                    font-weight: bold;
                    border-radius: 50%;
                    width: 28px;
                    height: 28px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-size: 12px;">
                    {rating}
                </div>
                """
                icon = folium.DivIcon(html=icon_html, icon_size=(28, 28))
                
                folium.Marker([station[2], station[3]], popup=popup_text, icon=icon).add_to(mymap)
                break


    folium_static(mymap)

# Основна функція для запуску додатка Streamlit
def main():
    st.title("Карта")
    st.sidebar.title("Пошук автозаправних станцій")
    
    # Поля введення в бічній панелі
    fuel_type = st.sidebar.selectbox("Оберіть тип пальва:", ('Дизель', 'Бензин'))
    gas_left = st.sidebar.number_input("Введіть кількість пального в баку (в літрах):")
    motor_power = st.sidebar.number_input("Введіть об'єм двигуна вашого автомобіля (в літрах):")
    location_str = st.sidebar.text_input("Введіть ваше місцезнаходження (місто, адреса і т. д.):")


    if not location_str:
        uuser_location = Nominatim(user_agent="gas_station_locator").geocode("Львів")
        mymmap = folium.Map(location=[uuser_location.latitude, uuser_location.longitude], zoom_start=12)
        folium_static(mymmap)

    if location_str:
        geolocator = Nominatim(user_agent="gas_station_locator")
        user_location = geolocator.geocode(location_str)

        if user_location:
            gas_stations, gas_stations_rating = fetch_gas_stations_from_db()  # Отримуємо дані про заправки та рейтинги

            max_distance = (gas_left / FUEL_CONSUMPTION[fuel_type.lower()]) * 100

            gas_stations_with_distances = [
                (station[0], station[1], calculate_distance((user_location.latitude, user_location.longitude), (station[2], station[3])))
                for station in gas_stations
                if calculate_distance((user_location.latitude, user_location.longitude), (station[2], station[3])) <= max_distance
            ]

            sorted_gas_stations = sorted(gas_stations_with_distances, key=lambda x: x[2])

            st.sidebar.subheader("Найближчі заправки:")
            fuel_needed_gas_station = []
            for idx, (station_id, station_name, distance) in enumerate(sorted_gas_stations[:5], start=1):
                fuel_needed = calculate_fuel_needed(distance, FUEL_CONSUMPTION[fuel_type.lower()], motor_power)
                if fuel_needed <= gas_left:
                    rating = gas_stations_rating.get(station_name, 'Н/Д')  # Отримуємо рейтинг для заправки
                    fuel_needed_gas_station.append((station_id, station_name, distance, rating, fuel_needed))  # Включаємо рейтинг
                    st.sidebar.write(f"{idx}. {station_name}")
                    st.sidebar.write(f"   - Відстань: {distance:.2f} км")
                    st.sidebar.write(f"   - Рейтинг: {rating}")  # Відображаємо рейтинг у бічній панелі
                    st.sidebar.write(f"   - Необхідне паливо: {fuel_needed:.2f} л")
            if not fuel_needed_gas_station:
                generate_map(user_location, gas_stations, [])
                st.sidebar.write("Немає заправок, досяжних на основі залишку палива.")
                return
            else:
                generate_map(user_location, gas_stations, fuel_needed_gas_station)
                if gas_stations_with_distances:
                    station_options = [str(idx) for idx in range(1, min(len(fuel_needed_gas_station)+1, 6))]  # Генеруємо варіанти для вибору
                    chosen_station = st.sidebar.selectbox("Виберіть номер заправки, до якої ви хочете поїхати:", station_options)
                else:
                    chosen_station = None
                if st.sidebar.button("Прокласти маршут"):
                    if 1 <= int(chosen_station) <= 5:
                        selected_station_id = sorted_gas_stations[int(chosen_station) - 1][0]
                        selected_gas_station = next((station for station in gas_stations if station[0] == selected_station_id), None)

                        if selected_gas_station:
                            gas_station_location = (selected_gas_station[2], selected_gas_station[3])
                            distance = calculate_distance((user_location.latitude, user_location.longitude), gas_station_location)
                            fuel_needed = calculate_fuel_needed(distance, FUEL_CONSUMPTION[fuel_type.lower()], motor_power)
                            station_name = selected_gas_station[1]
                            rating = gas_stations_rating.get(station_name, 'Н/Д')  # Отримуємо рейтинг для обраної заправки

                            st.sidebar.write(f"Відстань до {station_name}: {distance:.2f} км")
                            st.sidebar.write(f"Рейтинг заправки: {rating}")
                            st.sidebar.write(f"Необхідне паливо: {fuel_needed:.2f} л")

                            # Відображення посилання на маршрутизацію
                            directions_url = f"https://www.google.com/maps/dir/?api=1&origin={user_location.latitude},{user_location.longitude}&destination={selected_gas_station[2]},{selected_gas_station[3]}&travelmode=driving"
                            st.sidebar.markdown(f"[Натисніть тут для отримання маршруту]({directions_url})")
                        else:
                            st.sidebar.write("Не вдалося знайти координати обраної заправки.")
                    else:
                        st.sidebar.write("Недійсний вибір. Будь ласка, виберіть дійсний номер заправки.")

if __name__ == "__main__":
    main()
