# AnIML & SiLA 2.0 Implementation Plan
**Branch:** `feature/animl-sila-compliance`
**Goal:** Commercial-ready SPR software with regulatory compliance
**Architecture:** Single codebase with tiered licensing (Free/Pro/Enterprise)

---

## Architecture Overview

### **Feature Tier Structure**

| Feature | Free | Pro | Enterprise |
|---------|------|-----|------------|
| Basic SPR acquisition | ✅ | ✅ | ✅ |
| Excel export | ✅ | ✅ | ✅ |
| Method Manager | ✅ | ✅ | ✅ |
| QC validation | ✅ | ✅ | ✅ |
| **AnIML export** | ❌ | ✅ | ✅ |
| **Audit trail** | ❌ | ✅ | ✅ |
| **Advanced analytics** | ❌ | ✅ | ✅ |
| **SiLA 2.0 integration** | ❌ | ❌ | ✅ |
| **LIMS integration** | ❌ | ❌ | ✅ |
| **Electronic signatures** | ❌ | ❌ | ✅ |
| **21 CFR Part 11 compliance** | ❌ | ❌ | ✅ |

### **Pricing Strategy**
- **Free tier**: Academic/research use - drives adoption
- **Pro tier**: $1,500-5,000/year - Commercial labs
- **Enterprise tier**: $10,000+/year - Pharma with full compliance

---

## Phase 1: Foundation (1-2 weeks) - Feature Flag System
**Status:** 🔲 Not Started
**Goal:** Establish licensing infrastructure and feature gating

### Deliverables
- [ ] Feature flag system with tiered licensing
- [ ] License validation mechanism
- [ ] UI components for upgrade prompts
- [ ] Settings panel for license management

### Files to Create
```
affilabs/config/feature_flags.py       # Feature tier definitions
affilabs/config/license_manager.py     # License validation
affilabs/widgets/license_dialog.py     # UI for license entry
license_template.json                  # Example license file format
```

### Integration Points
- Add `self.features` to Application class in main.py
- Gate existing features (mark some as Pro/Enterprise)
- Add "Upgrade" buttons in UI for locked features

### Implementation Notes
```python
# Example feature flag usage
class FeatureFlags:
    def __init__(self, tier=FeatureTier.FREE):
        self.tier = tier

    @property
    def animl_export(self):
        return self.tier in [FeatureTier.PRO, FeatureTier.ENTERPRISE]

    @property
    def sila_integration(self):
        return self.tier == FeatureTier.ENTERPRISE
```

---

## Phase 2: AnIML Export Foundation (2-3 weeks)
**Status:** 🔲 Not Started
**Goal:** Basic AnIML XML export for SPR data
**Feature Flag:** `animl_export` (Pro tier)

### Deliverables
- [ ] AnIML exporter service
- [ ] Method → AnIML conversion
- [ ] Cycle data → AnIML samples
- [ ] QC results → AnIML validation

### Files to Create
```
affilabs/exporters/animl_exporter.py      # Core AnIML generator
affilabs/exporters/animl_templates.py     # XML templates
affilabs/exporters/animl_validator.py     # Schema validation
```

### Dependencies
```bash
pip install lxml xmlschema
```

### Integration Points
- Add "Export AnIML" button to Export Builder tab
- Extend `excel_exporter.py` to call AnIML exporter
- Feature-gate button with upgrade prompt for Free tier

### AnIML Structure
```xml
<AnIML>
  <ExperimentStepSet>
    <ExperimentStep name="SPR Binding Assay">
      <Method>
        <Author>...</Author>
        <Device>ezControl SPR</Device>
        <Software>ezControl v4.0</Software>
      </Method>
      <Result>
        <SeriesSet>
          <Series name="Channel A" seriesType="Float32">
            <IndividualValueSet>...</IndividualValueSet>
          </Series>
        </SeriesSet>
      </Result>
    </ExperimentStep>
  </ExperimentStepSet>
</AnIML>
```

---

## Phase 3: Audit Trail System (2-3 weeks)
**Status:** 🔲 Not Started
**Goal:** Track all user actions and data modifications
**Feature Flag:** `audit_trail` (Pro tier)

### Deliverables
- [ ] Audit log database (SQLite)
- [ ] Event tracking for all critical operations
- [ ] Audit log viewer UI
- [ ] Export audit logs to PDF/CSV

### Files to Create
```
affilabs/services/audit_service.py        # Audit logging
affilabs/widgets/audit_log_viewer.py      # UI for viewing logs
audit_logs.db                             # SQLite database
```

### Events to Track
- Method creation/modification/deletion
- Cycle start/stop/modification
- Data export (Excel, AnIML, CSV)
- Calibration changes
- QC pass/fail decisions
- User login (if multi-user implemented)

### Database Schema
```sql
CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY,
    timestamp DATETIME NOT NULL,
    user TEXT NOT NULL,
    action TEXT NOT NULL,
    entity_type TEXT,
    entity_id TEXT,
    old_value TEXT,
    new_value TEXT,
    status TEXT,
    notes TEXT
);
```

### Integration Points
- Wrap critical operations with `@audit_log` decorator
- Add "Audit Log" menu item to main window
- Show audit summary in QC reports

---

## Phase 4: Enhanced AnIML (1-2 weeks)
**Status:** 🔲 Not Started
**Goal:** Add metadata, signatures, compliance features
**Feature Flag:** `animl_export` (Pro tier)

### Deliverables
- [ ] Instrument metadata in AnIML
- [ ] Method parameters preservation
- [ ] Sample genealogy tracking
- [ ] Validation status in XML

### Enhancements
- Add device serial numbers, firmware versions
- Include calibration certificates
- Link QC validation results
- Add user/operator information
- Include audit trail references

### Example Enhanced AnIML
```xml
<Device>
  <Name>ezControl SPR</Name>
  <SerialNumber>FLMT09788</SerialNumber>
  <FirmwareVersion>2.2.0</FirmwareVersion>
  <Manufacturer>Affilabs</Manufacturer>
  <CalibrationDate>2026-01-15</CalibrationDate>
  <CalibrationCertificate>CAL-2026-001</CalibrationCertificate>
</Device>
```

---

## Phase 5: SiLA 2.0 Device Interfaces (3-4 weeks)
**Status:** 🔲 Not Started
**Goal:** Standardized device communication protocol
**Feature Flag:** `sila_integration` (Enterprise tier)

### Deliverables
- [ ] SiLA 2.0 server for ezControl
- [ ] Device feature definitions
- [ ] Command/property mappings
- [ ] Error handling and reporting

### Files to Create
```
affilabs/sila/sila_server.py                      # gRPC server
affilabs/sila/features/pump_control.sila.xml      # Pump interface
affilabs/sila/features/detector_control.sila.xml  # Detector interface
affilabs/sila/adapters/pump_adapter.py            # Pump-to-SiLA adapter
affilabs/sila/adapters/detector_adapter.py        # Detector-to-SiLA adapter
```

### Dependencies
```bash
pip install sila2 grpcio grpcio-tools protobuf
```

### SiLA Features to Implement
- **PumpControl**: SetFlowRate, StartPump, StopPump, GetStatus
- **DetectorControl**: GetSignal, SetIntegrationTime, Calibrate
- **TemperatureControl**: SetTemperature, GetTemperature
- **ValveControl**: SetPosition, GetPosition

### Integration Points
- Start SiLA server on application launch (if licensed)
- Expose current device state via SiLA properties
- Map existing commands to SiLA interface
- Add SiLA connection status indicator in UI

---

## Phase 6: LIMS Integration (2-3 weeks)
**Status:** 🔲 Not Started
**Goal:** Export to enterprise LIMS systems
**Feature Flag:** `lims_integration` (Enterprise tier)

### Deliverables
- [ ] LIMS export templates (generic format)
- [ ] Sample tracking integration
- [ ] Results auto-upload
- [ ] Configurable field mapping

### Files to Create
```
affilabs/integrations/lims_connector.py       # Generic LIMS API
affilabs/integrations/lims_mappers.py         # Field mapping
affilabs/config/lims_config.json              # Connection settings
affilabs/widgets/lims_settings_dialog.py      # Configuration UI
```

### Common LIMS Targets
- LabWare LIMS
- Thermo Scientific SampleManager
- Waters NuGenesis SDMS
- Generic REST API (configurable)

### LIMS Integration Flow
```
1. User completes cycle
2. System generates results
3. Auto-map to LIMS fields (configurable)
4. Upload via REST API / SOAP / file drop
5. Log success/failure in audit trail
```

### Configuration Example
```json
{
  "lims_type": "rest_api",
  "endpoint": "https://lims.company.com/api/v1",
  "api_key": "encrypted_key",
  "field_mapping": {
    "sample_id": "cycle.note",
    "assay_type": "cycle.type",
    "result_value": "cycle.final_ru",
    "operator": "user.name"
  }
}
```

---

## Phase 7: 21 CFR Part 11 Compliance (3-4 weeks)
**Status:** 🔲 Not Started
**Goal:** FDA-ready electronic records and signatures
**Feature Flag:** `cfr_part11_compliance` (Enterprise tier)

### Deliverables
- [ ] Electronic signature module
- [ ] User authentication system
- [ ] Role-based access control (RBAC)
- [ ] Data integrity verification (checksums)
- [ ] Audit trail review workflow

### Files to Create
```
affilabs/auth/user_manager.py                 # User accounts
affilabs/auth/signature_service.py            # E-signatures
affilabs/auth/rbac.py                         # Permissions
affilabs/widgets/signature_dialog.py          # Signature capture
affilabs/widgets/user_management_dialog.py    # Admin UI
users.db                                      # User database (SQLite)
```

### 21 CFR Part 11 Requirements
1. **User Authentication**: Password-protected accounts
2. **Electronic Signatures**: Signed before critical actions (method approval, data export)
3. **Non-repudiation**: Cryptographic signatures on records
4. **Audit Trails**: Who/what/when for all changes
5. **Data Integrity**: Checksums, tamper detection
6. **Access Controls**: Role-based permissions (Operator, Supervisor, Admin)

### User Roles
- **Operator**: Run methods, view data (no export, no method edit)
- **Supervisor**: Approve methods, review data, export results
- **Admin**: User management, system configuration, calibration

### Signature Points
- Method approval before first use
- QC report approval
- Data export (AnIML, Excel, LIMS)
- Calibration certificate approval
- Audit trail review (weekly/monthly)

### Cryptographic Signature
```python
# Hash data + user + timestamp
signature = sha256(data + user_id + timestamp + secret_key)
# Store signature with record
# Verify on retrieval
```

---

## Implementation Order

```
Start → Phase 1 (Foundation)
           ↓
        Phase 2 (Basic AnIML)
           ↓
        Phase 3 (Audit Trail)
           ↓
        Phase 4 (Enhanced AnIML)
           ↓
        Phase 5 (SiLA) OR Phase 6 (LIMS) [parallel or sequential]
           ↓
        Phase 7 (21 CFR Part 11)
```

### Quick Wins Timeline
- **4-5 weeks**: Phase 1 + 2 = Marketable "Pro" version with AnIML export
- **7-8 weeks**: Phase 1 + 2 + 3 = "Pro Plus" with audit trail
- **15-18 weeks**: All phases = "Enterprise" with full compliance

---

## Testing Strategy

### Phase 1 Testing
- [ ] Verify Free tier restricts Pro features
- [ ] Test license file parsing
- [ ] Validate upgrade prompts appear correctly
- [ ] Test license expiration handling

### Phase 2 Testing
- [ ] Validate AnIML against official schema
- [ ] Test round-trip (export → import in compliant software)
- [ ] Verify all metadata is preserved
- [ ] Test with large datasets (1000+ cycles)

### Phase 3 Testing
- [ ] Verify all critical operations are logged
- [ ] Test audit log search and filtering
- [ ] Validate timestamp accuracy
- [ ] Test concurrent logging (thread-safe)

### Phase 7 Testing
- [ ] Test signature verification
- [ ] Attempt data tampering (should fail validation)
- [ ] Test role-based access restrictions
- [ ] Validate audit trail completeness

---

## Dependencies & Libraries

### Required Packages
```bash
# Phase 2: AnIML
pip install lxml xmlschema

# Phase 5: SiLA 2.0
pip install sila2 grpcio grpcio-tools protobuf

# Phase 7: Cryptography
pip install cryptography pyjwt bcrypt

# Optional: Advanced features
pip install pydantic  # Data validation
pip install sqlalchemy  # ORM for databases
```

### External Standards
- **AnIML**: [ASTM E2078-18](https://www.astm.org/e2078-18.html)
- **SiLA 2.0**: [https://sila-standard.com](https://sila-standard.com)
- **21 CFR Part 11**: [FDA Guidance](https://www.fda.gov/regulatory-information/search-fda-guidance-documents/part-11-electronic-records-electronic-signatures-scope-and-application)

---

## Success Metrics

### Phase 1
- ✅ License system functional
- ✅ UI shows tiered features
- ✅ Upgrade prompts work

### Phase 2
- ✅ AnIML validates against schema
- ✅ Export completes in <10s for typical dataset
- ✅ Readable in 3rd-party AnIML viewers

### Phase 3
- ✅ 100% of critical operations logged
- ✅ Audit log searchable and exportable
- ✅ No performance degradation from logging

### Phase 7
- ✅ Passes FDA validation audit (if applicable)
- ✅ All signatures cryptographically secure
- ✅ Zero data tampering possible

---

## Notes & References

### Current Branch
```bash
git checkout feature/animl-sila-compliance
```

### Related Documentation
- See `METHOD_MANAGER_README.md` for method management context
- See `GIT_WORKFLOW.md` for branching strategy
- See `ERROR_HANDLING_PATTERNS.md` for error handling conventions

### Business Considerations
- Free tier builds community and drives adoption
- Pro tier targets commercial labs and core facilities
- Enterprise tier targets regulated pharma/biotech
- Consider subscription vs perpetual licensing
- Consider hardware-locked vs floating licenses

---

**Last Updated:** January 31, 2026
**Branch:** feature/animl-sila-compliance
**Next Step:** Implement Phase 1 - Feature Flag System
