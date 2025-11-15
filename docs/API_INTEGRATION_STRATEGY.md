# API Integration Strategy - Knauer Azura Autosampler

## Overview
This document outlines the strategy for creating a REST API that enables the Knauer Azura autosampler C# software to communicate with the PicoEZSPR Python-based SPR control system.

## Business Context
**OEM Requirement**: *"If we get a C# library that implements the communication protocol, it will reduce the support time on our side"*

The Knauer Azura autosampler requires integration with our Python-based SPR instrument control system. Rather than porting our entire Python codebase to C#, we will provide a REST API layer that allows the C# autosampler software to communicate seamlessly with our instrument control backend.

## System Configuration

**OEM Question**: *"As we understood from the protocol, we should control a Raspberry Pi PC that manages the valves and pump. Is this configuration fixed? Please define the system configuration"*

**Answer**: The configuration is flexible. We recommend the following architecture for Knauer Azura integration:

### PicoEZSPR System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Laptop (Windows)                      │
│                                                          │
│  ┌────────────────────────────────────────────────┐    │
│  │  AffinitéLab Suite (Python/PySide6)            │    │
│  │  - User Interface                              │    │
│  │  - Data Processing & Analysis                  │    │
│  │  - Method Management                           │    │
│  │  - ELN & Reporting                             │    │
│  └──────────────────┬─────────────────────────────┘    │
│                     │                                    │
│              Single USB-C Cable                          │
│              (USB Ethernet Gadget - TCP/IP)              │
└─────────────────────┼────────────────────────────────────┘
                      │
┌─────────────────────▼────────────────────────────────────┐
│            PicoEZSPR (Main Control Unit)                 │
│            Based on Raspberry Pi 4/5                     │
│                                                          │
│  ┌────────────────────────────────────────────────┐    │
│  │  Embedded Control Software (Python)            │    │
│  │  - SPR Measurement Control                     │    │
│  │  - Ocean Optics Spectrometer Interface         │    │
│  │  - Tecan Cavro Centris Pump Control            │    │
│  │  - Knauer Azura Communication                  │    │
│  │  - REST API Server (FastAPI)                   │    │
│  │  - USB-C Device Mode (Ethernet Gadget)         │    │
│  └────────────────────────────────────────────────┘    │
│                                                          │
│  Internal Connections:                                   │
│  ├─ Ocean Optics Spectrometer (USB 3.0)                 │
│  ├─ Tecan Cavro Centris (Serial/USB) ← Power from unit  │
│  ├─ Knauer Azura (Serial/USB) ← Comms only              │
│  ├─ SPR Optical Components                              │
│  └─ Temperature Sensors & Control                       │
│                                                          │
│  Power Input: 24V DC @ 3A (72W)                         │
│  Power Distribution:                                     │
│  ├─ 24V Direct → Tecan Cavro Centris (~36W)             │
│  ├─ 5V/3A (Buck) → Raspberry Pi 4/5 (~15W)              │
│  └─ 5V/2A (Buck) → USB Hub & Peripherals (~10W)         │
└──────────────────────┬──────────────────────────────────┘
                       │ Power + Comms
                       ▼
              ┌────────────────────┐
              │  Tecan Cavro       │
              │  Centris Pump      │
              │  (24V powered by   │
              │   PicoEZSPR)       │
              └────────────────────┘

              ┌────────────────────┐
              │  Knauer Azura      │
              │  Autosampler       │
              │  (Own 24V power,   │◄──── External 24V PSU
              │   comms only)      │
              └────────────────────┘
```

### Key Design Decisions

**1. Raspberry Pi 4 or 5 (NOT Pico)**
- **Why?** USB host capability required for Ocean Optics spectrometer
- **Why?** Full Linux OS needed for OceanDirect SDK
- **Why?** Sufficient RAM (4-8GB) for data processing and ML models
- **Why?** Full Python ecosystem (FastAPI, NumPy, SciPy, scikit-learn)
- **Why?** Multi-tasking: simultaneous instrument control, API server, data logging

**2. 24V Power System**
- **Input:** 24V DC @ 3A minimum (72W)
- **Tecan Cavro Centris:** Requires 24V (powered directly from PicoEZSPR)
- **Raspberry Pi 4/5:** 5V via buck converter from 24V
- **Knauer Azura:** Own power supply (external 24V)

**3. Single USB-C Connection to Laptop**
- USB Ethernet Gadget mode (RPi appears as network adapter)
- TCP/IP communication over USB-C cable
- Standard REST API (no special drivers needed)
- Works on Windows, Mac, Linux

**4. Hardware Integration**
- **Ocean Optics:** USB 3.0 to RPi (internal to PicoEZSPR)
- **Tecan Pump:** Serial/USB to RPi + 24V power from PicoEZSPR
- **Knauer Azura:** Serial/USB to RPi (comms only, own power)

## Architecture

### Current System
- **AffinitéLab Suite**: Python-based SPR control system
- **GUI**: PySide6 (Qt for Python)
- **Instrument Control**: Ocean Optics spectrometers via OceanDirect API
- **Data Processing**: NumPy, SciPy, pandas
- **Storage**: SQLite/PostgreSQL

### Integration Approach
```
┌─────────────────────────────────────┐
│   Knauer Azura Autosampler (C#)    │
│   - Sample handling                 │
│   - Position control                │
│   - Workflow management             │
└──────────────┬──────────────────────┘
               │ HTTP/REST
               │ (JSON over HTTPS)
               ▼
┌─────────────────────────────────────┐
│   AffinitéLab REST API (Python)     │
│   - FastAPI framework               │
│   - Authentication & authorization  │
│   - Request validation              │
│   - Error handling                  │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│   AffinitéLab Core (Python)         │
│   - Instrument control              │
│   - SPR measurements                │
│   - Data acquisition                │
│   - Method execution                │
│   - Calibration management          │
└─────────────────────────────────────┘
```

## Technical Implementation

### REST API Framework: FastAPI

**Why FastAPI:**
- ✅ High performance (async/await support)
- ✅ Automatic OpenAPI/Swagger documentation
- ✅ Built-in request validation (Pydantic models)
- ✅ Modern Python async features
- ✅ Easy to integrate with existing Python code
- ✅ Type hints for better IDE support
- ✅ Industry-standard REST API patterns

### API Endpoints

#### 1. Instrument Management
```
GET    /api/v1/instruments              # List available SPR instruments
POST   /api/v1/instruments/{id}/connect # Connect to instrument
DELETE /api/v1/instruments/{id}/connect # Disconnect from instrument
GET    /api/v1/instruments/{id}/status  # Get instrument status
GET    /api/v1/instruments/{id}/info    # Get instrument information
```

#### 2. Method Management
```
GET    /api/v1/methods                  # List available methods
GET    /api/v1/methods/{id}             # Get method details
POST   /api/v1/methods                  # Create new method
PUT    /api/v1/methods/{id}             # Update method
DELETE /api/v1/methods/{id}             # Delete method
```

#### 3. Measurement Control
```
POST   /api/v1/measurements/start       # Start SPR measurement
GET    /api/v1/measurements/{id}/status # Get measurement status
POST   /api/v1/measurements/{id}/stop   # Stop measurement
GET    /api/v1/measurements/{id}/data   # Get measurement data
```

#### 4. Sample Management (Autosampler Integration)
```
POST   /api/v1/samples/prepare          # Prepare for sample
POST   /api/v1/samples/measure          # Measure current sample
GET    /api/v1/samples/{id}/results     # Get sample results
POST   /api/v1/samples/batch            # Execute batch measurement
```

#### 5. Calibration
```
GET    /api/v1/calibration              # Get calibration status
POST   /api/v1/calibration/led          # Run LED calibration
POST   /api/v1/calibration/reference    # Run reference calibration
GET    /api/v1/calibration/history      # Get calibration history
```

#### 6. Data Export
```
GET    /api/v1/export/results/{id}      # Export measurement results
GET    /api/v1/export/batch/{batch_id}  # Export batch results
POST   /api/v1/export/custom            # Custom data export
```

### Data Models (Request/Response)

#### InstrumentInfo
```json
{
  "id": "string",
  "serial_number": "string",
  "model": "string",
  "connected": true,
  "status": "idle|measuring|error",
  "temperature": 25.3,
  "firmware_version": "1.2.3",
  "last_calibration": "2025-10-20T10:30:00Z"
}
```

#### MeasurementRequest
```json
{
  "method_id": "string",
  "sample_id": "string",
  "sample_name": "Sample A1",
  "integration_time_ms": 100,
  "scans_to_average": 3,
  "wavelength_range": {
    "start": 400,
    "end": 800
  },
  "metadata": {
    "operator": "string",
    "project": "string",
    "notes": "string"
  }
}
```

#### MeasurementResult
```json
{
  "measurement_id": "string",
  "sample_id": "string",
  "timestamp": "2025-10-20T10:30:00Z",
  "status": "completed|failed|in_progress",
  "wavelengths": [400.1, 400.2, ...],
  "intensities": [1234.5, 1235.6, ...],
  "spr_angle": 45.3,
  "binding_response": 123.4,
  "quality_metrics": {
    "signal_to_noise": 45.6,
    "baseline_stability": 0.98
  },
  "metadata": { ... }
}
```

#### BatchMeasurementRequest
```json
{
  "batch_id": "string",
  "method_id": "string",
  "samples": [
    {
      "position": "A1",
      "sample_id": "sample_001",
      "sample_name": "Control",
      "parameters": { ... }
    },
    {
      "position": "A2",
      "sample_id": "sample_002",
      "sample_name": "Test 1",
      "parameters": { ... }
    }
  ],
  "options": {
    "pause_between_samples": 30,
    "auto_calibrate": true,
    "export_format": "csv"
  }
}
```

## C# Client Library

### NuGet Package: AffiniteLab.Client

**Features:**
- Async/await support for all operations
- Strongly-typed request/response models
- Automatic retry logic with exponential backoff
- Connection pooling and timeout management
- Comprehensive error handling
- Event-based progress reporting
- Built-in logging integration

**Example Usage:**
```csharp
using AffiniteLab.Client;

// Initialize client
var client = new AffiniteLabClient("http://localhost:8000");

// Discover instruments
var instruments = await client.GetInstrumentsAsync();
var instrument = instruments.FirstOrDefault();

// Connect to instrument
await client.ConnectInstrumentAsync(instrument.Id);

// Prepare measurement
var request = new MeasurementRequest
{
    MethodId = "method_001",
    SampleId = "A1",
    SampleName = "Control Sample",
    IntegrationTimeMs = 100,
    ScansToAverage = 3
};

// Start measurement
var measurementId = await client.StartMeasurementAsync(request);

// Monitor progress
client.MeasurementProgress += (sender, args) =>
{
    Console.WriteLine($"Progress: {args.PercentComplete}%");
};

// Wait for completion
var result = await client.WaitForMeasurementAsync(measurementId);

// Process results
Console.WriteLine($"SPR Angle: {result.SprAngle}");
Console.WriteLine($"Binding Response: {result.BindingResponse}");
```

### Batch Processing Example
```csharp
// Define batch
var batch = new BatchMeasurementRequest
{
    BatchId = Guid.NewGuid().ToString(),
    MethodId = "method_001",
    Samples = new List<SampleMeasurement>
    {
        new() { Position = "A1", SampleId = "ctrl_001", SampleName = "Control" },
        new() { Position = "A2", SampleId = "test_001", SampleName = "Test 1" },
        new() { Position = "A3", SampleId = "test_002", SampleName = "Test 2" }
    },
    Options = new BatchOptions
    {
        PauseBetweenSamples = 30,
        AutoCalibrate = true,
        ExportFormat = "csv"
    }
};

// Execute batch
await client.ExecuteBatchAsync(batch);

// Get results
var results = await client.GetBatchResultsAsync(batch.BatchId);
```

## Security & Authentication

### Authentication Strategy
- **API Key**: Simple token-based authentication for initial deployment
- **OAuth 2.0**: For future cloud deployments
- **TLS/HTTPS**: All communication encrypted

### Implementation
```python
from fastapi import Security, HTTPException
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(name="X-API-Key")

async def verify_api_key(api_key: str = Security(api_key_header)):
    if api_key not in valid_api_keys:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return api_key
```

### Authorization Levels
- **Read-only**: View status, get results
- **Operator**: Start/stop measurements
- **Administrator**: Calibration, method management, configuration

## Error Handling

### Standard Error Response
```json
{
  "error": {
    "code": "INSTRUMENT_NOT_CONNECTED",
    "message": "Instrument serial FL12345 is not connected",
    "details": {
      "instrument_id": "FL12345",
      "timestamp": "2025-10-20T10:30:00Z"
    },
    "trace_id": "abc123def456"
  }
}
```

### HTTP Status Codes
- `200 OK`: Successful request
- `201 Created`: Resource created
- `400 Bad Request`: Invalid request parameters
- `401 Unauthorized`: Missing or invalid authentication
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Resource not found
- `409 Conflict`: Resource conflict (e.g., measurement already running)
- `500 Internal Server Error`: Server-side error
- `503 Service Unavailable`: Instrument not available

### C# Error Handling
```csharp
try
{
    var result = await client.StartMeasurementAsync(request);
}
catch (InstrumentNotConnectedException ex)
{
    // Handle disconnected instrument
    await client.ConnectInstrumentAsync(ex.InstrumentId);
    // Retry
}
catch (MeasurementInProgressException ex)
{
    // Handle concurrent measurement
    await client.WaitForMeasurementAsync(ex.MeasurementId);
}
catch (AffiniteLabApiException ex)
{
    // Handle general API errors
    Console.WriteLine($"Error: {ex.Message}");
}
```

## Real-Time Communication

### WebSocket Support (Optional)
For real-time updates during measurements:

```python
from fastapi import WebSocket

@app.websocket("/ws/measurements/{measurement_id}")
async def measurement_stream(websocket: WebSocket, measurement_id: str):
    await websocket.accept()
    async for data_point in acquire_spectrum_stream(measurement_id):
        await websocket.send_json(data_point)
```

```csharp
// C# WebSocket client
var ws = new ClientWebSocket();
await ws.ConnectAsync(new Uri("ws://localhost:8000/ws/measurements/123"), CancellationToken.None);

while (ws.State == WebSocketState.Open)
{
    var buffer = new byte[4096];
    var result = await ws.ReceiveAsync(new ArraySegment<byte>(buffer), CancellationToken.None);
    var json = Encoding.UTF8.GetString(buffer, 0, result.Count);
    var dataPoint = JsonSerializer.Deserialize<DataPoint>(json);
    // Process real-time data
}
```

## Documentation

### Auto-Generated API Documentation
FastAPI automatically generates:
- **OpenAPI 3.0 specification**: Machine-readable API definition
- **Swagger UI**: Interactive API testing interface at `/docs`
- **ReDoc**: Alternative documentation at `/redoc`

### Developer Documentation
- API reference guide
- Integration tutorials
- Sample code (C#, Python, JavaScript)
- Troubleshooting guide
- Best practices

### Knauer Integration Guide
Specific documentation for Knauer Azura integration:
1. Installation and setup
2. Authentication configuration
3. Sample workflow integration
4. Error handling and recovery
5. Performance optimization
6. Support contact information

## Deployment Options

### Option 1: Embedded API Server (Recommended for Initial Deployment)
- API server runs alongside AffinitéLab GUI application
- Single installation, no separate deployment needed
- Localhost communication (127.0.0.1)
- Automatic startup with GUI

### Option 2: Standalone API Service
- API runs as separate Windows service
- Independent of GUI application
- Can run on dedicated server
- Multiple clients can connect

### Option 3: Cloud-Hosted API (Future)
- API hosted on Azure
- Remote instrument control
- Multi-tenant support
- Enterprise monitoring

## Performance Considerations

### Optimization Strategies
1. **Connection Pooling**: Reuse instrument connections
2. **Async Operations**: Non-blocking I/O for all operations
3. **Caching**: Cache calibration data and method definitions
4. **Compression**: gzip compression for large data transfers
5. **Rate Limiting**: Prevent API abuse

### Expected Performance
- **Latency**: < 50ms for status requests
- **Throughput**: 100+ requests/second
- **Concurrent Measurements**: Support for 4+ instruments
- **Data Transfer**: 10MB/s+ for spectrum data

## Testing Strategy

### Unit Tests
- API endpoint testing
- Request validation
- Error handling
- Authentication/authorization

### Integration Tests
- End-to-end workflow testing
- Knauer autosampler integration
- Batch processing scenarios
- Error recovery

### Load Testing
- Concurrent request handling
- Large batch processing
- Long-running measurements
- Memory leak detection

### C# Client Tests
- NuGet package testing
- Async/await behavior
- Error handling
- Timeout management

## Implementation Timeline

### Phase 1: Core API (Months 1-2)
- [ ] FastAPI project setup
- [ ] Instrument management endpoints
- [ ] Basic measurement control
- [ ] Authentication implementation
- [ ] Error handling framework
- [ ] Swagger documentation

### Phase 2: Advanced Features (Months 3-4)
- [ ] Batch measurement support
- [ ] Real-time WebSocket streaming
- [ ] Calibration endpoints
- [ ] Data export functionality
- [ ] Method management
- [ ] Performance optimization

### Phase 3: C# Client Library (Months 5-6)
- [ ] C# client library development
- [ ] NuGet package creation
- [ ] Async/await implementation
- [ ] Error handling and retry logic
- [ ] Event-based progress reporting
- [ ] Comprehensive examples

### Phase 4: Knauer Integration (Month 7)
- [ ] Knauer-specific workflow integration
- [ ] Sample position mapping
- [ ] Batch file format support
- [ ] Integration testing with Knauer team
- [ ] Documentation and training
- [ ] Beta testing with OEM

### Phase 5: Production Release (Month 8)
- [ ] Security audit
- [ ] Performance benchmarking
- [ ] Load testing
- [ ] Documentation finalization
- [ ] OEM training and handoff
- [ ] Production deployment

## Cost Estimate

### Development Costs
- **Phase 1-2 (Core API)**: 3-4 weeks @ $10k/week = **$30k-40k**
- **Phase 3 (C# Library)**: 2-3 weeks @ $10k/week = **$20k-30k**
- **Phase 4 (Knauer Integration)**: 2 weeks @ $10k/week = **$20k**
- **Phase 5 (Production)**: 1 week @ $10k/week = **$10k**

**Total Development Cost**: **$80k-100k**

### Infrastructure Costs
- **Development Server**: $500/month × 8 months = **$4k**
- **Testing Environment**: $300/month × 6 months = **$1.8k**
- **CI/CD Pipeline**: $200/month × 8 months = **$1.6k**

**Total Infrastructure Cost**: **$7.4k**

### Personnel Costs
- **Python/FastAPI Developer**: 1 FTE × 6 months
- **C# Developer**: 0.5 FTE × 3 months
- **QA Engineer**: 0.25 FTE × 4 months
- **Technical Writer**: 0.25 FTE × 2 months

### Total Project Cost: **$90k-110k**

## Benefits

### For Knauer (OEM)
- ✅ **Reduced Support Time**: Well-documented, standard REST API
- ✅ **Easy Integration**: Native C# library with examples
- ✅ **No Python Dependency**: No need to learn Python or maintain Python code
- ✅ **Flexibility**: Can integrate with any language in the future
- ✅ **Standard Protocol**: Industry-standard REST/JSON communication

### For Affinité Instruments
- ✅ **Maintain Python Advantage**: Keep ML/AI capabilities, rapid development
- ✅ **Single Codebase**: No need to maintain duplicate C# codebase
- ✅ **Future-Proof**: Easy to add new OEM integrations
- ✅ **Cloud-Ready**: API can be deployed locally or in cloud
- ✅ **Scalable**: Can support multiple instruments and clients

### For End Users
- ✅ **Seamless Integration**: Autosampler and SPR work together smoothly
- ✅ **Automated Workflows**: Batch processing with minimal user intervention
- ✅ **Reliable Operation**: Robust error handling and recovery
- ✅ **Data Quality**: Standardized data formats and validation

## Risks & Mitigation

### Technical Risks
| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Performance bottlenecks | High | Medium | Load testing, profiling, optimization |
| Network reliability | Medium | Medium | Retry logic, offline queuing |
| API breaking changes | High | Low | Versioning, deprecation policy |
| Security vulnerabilities | High | Low | Security audit, penetration testing |

### Business Risks
| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| OEM requirements change | Medium | Medium | Agile development, frequent check-ins |
| Timeline delays | Medium | Medium | Phased delivery, MVP approach |
| Integration issues | High | Low | Early prototype, beta testing |
| Support burden | Medium | Low | Comprehensive documentation, training |

## Success Metrics

### Technical Metrics
- API uptime: > 99.9%
- Average response time: < 100ms
- Error rate: < 0.1%
- Test coverage: > 90%

### Business Metrics
- OEM support tickets: < 5/month
- Integration time: < 2 weeks for new installations
- Customer satisfaction: > 4.5/5
- API adoption: > 80% of new installations

## Support & Maintenance

### Support Levels
- **Level 1**: Documentation, FAQs, email support
- **Level 2**: Phone support, remote debugging
- **Level 3**: On-site support, custom integration

### Maintenance Plan
- Quarterly security updates
- Monthly feature releases
- Weekly bug fixes (critical issues)
- Annual API version upgrades

### Documentation Updates
- API changelog for every release
- Migration guides for breaking changes
- Updated examples and tutorials
- Video tutorials and webinars

## Future Enhancements

### Phase 2 Features (Year 2)
- GraphQL API for flexible data queries
- gRPC for high-performance communication
- Multi-instrument orchestration
- Advanced scheduling and queuing
- Machine learning integration

### Cloud Features
- Azure-hosted API service
- Multi-tenant support
- Global load balancing
- Advanced analytics dashboard
- Remote instrument monitoring

## Conclusion

This API integration strategy provides a comprehensive approach to connecting the Knauer Azura autosampler C# software with the AffinitéLab Python-based SPR control system. By implementing a REST API with a native C# client library, we can:

1. **Reduce OEM support burden** through well-documented, standard interfaces
2. **Maintain our Python advantage** for ML/AI and rapid development
3. **Enable future integrations** with other OEM partners and platforms
4. **Provide a scalable foundation** for cloud deployment and enterprise features

The phased implementation approach ensures we can deliver value incrementally while managing risk and maintaining quality.

## References & Resources

### Technical Documentation
- FastAPI: https://fastapi.tiangolo.com/
- OpenAPI Specification: https://swagger.io/specification/
- REST API Best Practices: https://restfulapi.net/
- C# HttpClient: https://docs.microsoft.com/en-us/dotnet/api/system.net.http.httpclient

### Integration Guides
- Ocean Optics OceanDirect API
- Knauer Azura Autosampler SDK
- AffinitéLab Core API Reference

### Standards & Compliance
- 21 CFR Part 11 (Electronic Records)
- ALCOA+ Data Integrity Principles
- ISO 9001 Quality Management

---

**Document Version**: 1.0
**Last Updated**: October 20, 2025
**Owner**: Affinité Instruments - Software Architecture Team
**Status**: Draft - Pending OEM Review
