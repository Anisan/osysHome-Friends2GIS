# Friends2GIS - 2GIS Friends Location Tracker

![Friends2GIS Icon](static/Friends2GIS.png)

WebSocket-based location tracking system for monitoring friends' locations from 2GIS Friends service.

## Description

The `Friends2GIS` module provides location tracking capabilities for the osysHome platform by connecting to 2GIS Friends WebSocket service. It enables real-time location monitoring and updates.

## Main Features

- ✅ **WebSocket Connection**: Real-time connection to 2GIS Friends service
- ✅ **Location Tracking**: Track friends' locations
- ✅ **Automatic Updates**: Real-time location updates
- ✅ **Reconnection**: Automatic reconnection on disconnect
- ✅ **Viewport Calculation**: Automatic viewport calculation for map display

## Admin Panel

The module provides an admin interface for:
- Viewing tracked friends
- Managing friend locations
- Configuring WebSocket connection

## Configuration

- **Token**: 2GIS Friends authentication token
- **Reconnect Interval**: Delay between reconnection attempts (default: 5 seconds)

## Usage

### Setting Up

1. Obtain 2GIS Friends token
2. Navigate to Friends2GIS module
3. Enter token in settings
4. Module connects automatically

## Technical Details

- **Protocol**: WebSocket (WSS)
- **Service**: 2GIS Friends API
- **Threading**: Separate thread for WebSocket connection
- **Reconnection**: Automatic reconnection handling

## Version

Current version: **0.2**

## Category

App

## Requirements

- Flask
- websocket-client
- SQLAlchemy
- osysHome core system

## Author

Eraser

## License

See the main osysHome project license

